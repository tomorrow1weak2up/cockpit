"""Intergation tests for ``cockpit.quantities``."""

import pytest
from cockpit import quantities
from cockpit.quantities import __all__
from cockpit.quantities.quantity import SingleStepQuantity
from cockpit.utils.schedules import linear
from tests.test_quantities.settings import PROBLEMS, PROBLEMS_IDS
from tests.utils.harness import SimpleTestHarness

QUANTITIES = [getattr(quantities, q) for q in __all__ if q != "Quantity"]
IDS = [q_cls.__name__ for q_cls in QUANTITIES]


@pytest.mark.parametrize("problem", PROBLEMS, ids=PROBLEMS_IDS)
@pytest.mark.parametrize("quantity_cls", QUANTITIES, ids=IDS)
def test_quantity_integration_and_track_events(problem, quantity_cls):
    """Check if ``Cockpit`` with a single quantity works.

    Args:
        problem (tests.utils.Problem): Settings for train loop.
        quantity_cls (Class): Quantity class that should be tested.
    """
    interval, offset = 1, 2
    schedule = linear(interval, offset=offset)
    quantity = quantity_cls(track_schedule=schedule, verbose=True)

    problem.set_up()
    iterations = problem.iterations
    testing_harness = SimpleTestHarness(problem)
    cockpit_kwargs = {"quantities": [quantity]}
    testing_harness.test(cockpit_kwargs)
    problem.tear_down()

    def is_track_event(iteration):
        if isinstance(quantity, SingleStepQuantity):
            return schedule(iteration)
        else:
            shift = quantity_cls._start_end_difference
            return schedule(iteration) and iteration + shift < iterations

    track_events = sorted(i for i in range(iterations) if is_track_event(i))
    output_events = sorted(quantity.get_output().keys())

    assert output_events == track_events
