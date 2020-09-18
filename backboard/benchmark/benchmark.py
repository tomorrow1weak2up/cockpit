from collections import defaultdict

import pandas
from torch.optim import SGD

from backboard.benchmark.utils import get_train_size
from backboard.cockpit_plotter import CockpitPlotter
from backboard.quantities import Time
from backboard.runners.scheduled_runner import ScheduleCockpitRunner
from deepobs.pytorch.config import set_default_device


def _check_timer(quantities, max_steps):
    """Run checks to make sure the benchmark has access to time information."""
    timers = [q for q in quantities if isinstance(q, Time)]
    num_timers = len(timers)

    if num_timers != 1:
        raise ValueError(f"Got {num_timers} Time quantities. Expect 1.")

    timer = timers[0]
    for step in [0, max_steps]:
        if not timer.is_active(step):
            raise ValueError(f"Time quantity must track at step {step}")


def _check_quantities(quantities):
    """Run checks on quantities to make sure the benchmark runs."""
    if quantities is None:
        raise ValueError("Expect list of quantities but got None")

    for q in quantities:
        if not q.output == defaultdict(dict):
            raise ValueError(
                f"Quantity {q} has already been used or not been initialized"
            )


def _make_runner(quantities):
    """Return a DeepOBS runner that tracks the specified quantities."""
    optimizer_class = SGD
    hyperparams = {
        "lr": {"type": float, "default": 0.001},
        "momentum": {"type": float, "default": 0.0},
        "nesterov": {"type": bool, "default": False},
    }

    return ScheduleCockpitRunner(
        optimizer_class, hyperparams, quantities=quantities, plot=False
    )


def _get_num_epochs(runner, testproblem, max_steps):
    """Convert maximum number of steps into number of epochs."""
    batch_size = runner._use_default(testproblem, "batch_size")
    train_size = get_train_size(testproblem)
    steps_per_epoch, _ = divmod(train_size, batch_size)

    num_epochs, rest = divmod(max_steps, steps_per_epoch)
    if rest > 0:
        num_epochs += 1

    return num_epochs


def constant_lr_schedule(num_epochs):
    """Constant learning rate schedule."""
    return lambda epoch: 1.0


def _read_tracking_data(runner):
    """Return the tracked data from a completed run of a runner.

    Abuses the CockpitPlotter to read data
    """
    plotter = CockpitPlotter(runner._get_cockpit_logpath())
    plotter._read_tracking_results()
    return plotter.tracking_data


def run_benchmark(testproblem, quantities, max_steps, random_seed):
    """Return average time per iteration.

    Args:
        testproblem (str): Label of a DeepOBS problem.
        quantities ([Quantity]): List of quantities used in the cockpit.
        max_steps (int): Maximum number of iterations used for average
            time estimation.
        random_seed (int): Random seed used at initialization.
    """
    _check_timer(quantities, max_steps)
    _check_quantities(quantities)

    runner = _make_runner(quantities)
    num_epochs = _get_num_epochs(runner, testproblem, max_steps)

    runner.run(
        testproblem=testproblem,
        num_epochs=num_epochs,
        l2_reg=0.0,  # necessary for backobs!
        lr_schedule=constant_lr_schedule,
        random_seed=random_seed,
        track_interval=float("nan"),  # irrelevant
        # turn plotting off, everything below is irrelevant
        plot_interval=float("nan"),
        show_plots=False,
        save_plots=False,
        save_final_plot=False,
        save_animation=False,
    )

    data = _read_tracking_data(runner)

    return extract_average_time(data, max_steps)


def extract_average_time(data, max_steps):
    """Extract average run time per iteration from tracked data."""
    data = data[["iteration", "time"]].dropna()
    data = data.loc[data["iteration"].isin([0, max_steps])]

    iterations = data["iteration"].to_list()
    values = data["time"].to_list()

    assert iterations == [0, max_steps]
    assert len(values) == 2

    return (values[1] - values[0]) / (iterations[1] - iterations[0])


def _check_max_steps(max_steps, track_interval, min_events=5):
    """Check max_steps is large enough to allow at least ``min_events`` trackings."""
    num_events = max_steps // track_interval
    if num_events < min_events:
        raise ValueError(
            f"max_steps is too small! Want {num_events}>={min_events} track events."
        )


def benchmark(
    testproblems,
    configs,
    track_intervals,
    num_seeds,
    devices,
    max_steps,
    savefile=None,
    header=None,
):
    """Benchmark the cockpit."""
    _check_max_steps(max_steps, track_interval=max(track_intervals))

    columns = [
        "testproblem",
        "quantities",
        "track_interval",
        "max_steps",
        "random_seed",
        "device",
        "time_per_step",
    ]
    data = pandas.DataFrame(columns=columns)

    for device in devices:
        set_default_device(device)

        for testproblem in testproblems:
            for name, config in configs.items():
                for track_interval in track_intervals:
                    for random_seed in range(num_seeds):
                        quantities = [q(track_interval=track_interval) for q in config]
                        runtime = run_benchmark(
                            testproblem, quantities, max_steps, random_seed
                        )

                        run_data = {
                            "testproblem": testproblem,
                            "quantities": name,
                            "track_interval": track_interval,
                            "max_steps": max_steps,
                            "random_seed": random_seed,
                            "device": device,
                            "time_per_step": runtime,
                        }
                        data = data.append(run_data, ignore_index=True)

    if savefile is not None:
        with open(savefile, "w") as f:
            if header is not None:
                header_comment = "\n".join("# " + line for line in header.splitlines())
                f.write(header_comment + "\n")
            data.to_csv(f)

    return data
