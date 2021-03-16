"""Compare ``TICDiag`` and ``TICTrace`` quantities with ``torch.autograd``."""

import pytest

from cockpit.context import get_individual_losses
from cockpit.quantities import TICDiag, TICTrace
from cockpit.utils.schedules import linear
from tests.test_quantities.settings import PROBLEMS, PROBLEMS_IDS
from tests.test_quantities.utils import (
    autograd_diag_hessian,
    autograd_individual_gradients,
    compare_quantities_separate_runs,
    compare_quantities_single_run,
)


class AutogradTICDiag(TICDiag):
    """``torch.autograd`` implementation of ``TICDiag``."""

    def extensions(self, global_step):
        """Return list of BackPACK extensions required for the computation.

        Args:
            global_step (int): The current iteration number.

        Returns:
            list: (Potentially empty) list with required BackPACK quantities.
        """
        return []

    def create_graph(self, global_step):
        """Return whether access to the forward pass computation graph is needed.

        Args:
            global_step (int): The current iteration number.

        Returns:
            bool: ``True`` if the computation graph shall not be deleted,
                else ``False``.
        """
        return self.should_compute(global_step)

    def _compute(self, global_step, params, batch_loss):
        """Evaluate the TIC approximating the Hessian by its diagonal.

        Args:
            global_step (int): The current iteration number.
            params ([torch.Tensor]): List of torch.Tensors holding the network's
                parameters.
            batch_loss (torch.Tensor): Mini-batch loss from current step.
        """
        losses = get_individual_losses(global_step)
        individual_gradients_flat = autograd_individual_gradients(
            losses, params, concat=True
        )

        if self._curvature == "diag_h":
            diag_curvature_flat = autograd_diag_hessian(batch_loss, params, concat=True)
        else:
            raise NotImplementedError("Only Hessian diagonal is implemented")

        N_axis = 0
        second_moment_flat = (individual_gradients_flat ** 2).mean(N_axis)

        return (second_moment_flat / (diag_curvature_flat + self._epsilon)).sum().item()


class AutogradTICTrace(TICTrace):
    """``torch.autograd`` implementation of ``TICTrace``."""

    def extensions(self, global_step):
        """Return list of BackPACK extensions required for the computation.

        Args:
            global_step (int): The current iteration number.

        Returns:
            list: (Potentially empty) list with required BackPACK quantities.
        """
        return []

    def create_graph(self, global_step):
        """Return whether access to the forward pass computation graph is needed.

        Args:
            global_step (int): The current iteration number.

        Returns:
            bool: ``True`` if the computation graph shall not be deleted,
                else ``False``.
        """
        return self.should_compute(global_step)

    def _compute(self, global_step, params, batch_loss):
        """Evaluate the TIC approximation proposed in thomas2020interplay.

        Args:
            global_step (int): The current iteration number.
            params ([torch.Tensor]): List of torch.Tensors holding the network's
                parameters.
            batch_loss (torch.Tensor): Mini-batch loss from current step.
        """
        losses = get_individual_losses(global_step)
        individual_gradients_flat = autograd_individual_gradients(
            losses, params, concat=True
        )

        if self._curvature == "diag_h":
            curvature_trace = autograd_diag_hessian(
                batch_loss, params, concat=True
            ).sum()
        else:
            raise NotImplementedError("Only Hessian trace is implemented")

        N_axis = 0
        mean_squared_l2_norm = (individual_gradients_flat ** 2).mean(N_axis).sum()

        return (mean_squared_l2_norm / (curvature_trace + self._epsilon)).item()


@pytest.mark.parametrize("problem", PROBLEMS, ids=PROBLEMS_IDS)
def test_tic_diag_single_run(problem):
    """Compare BackPACK and ``torch.autograd`` implementation of TICDiag.

    Both quantities run simultaneously in the same cockpit.

    Args:
        problem (tests.utils.Problem): Settings for train loop.
    """
    interval, offset = 1, 2
    schedule = linear(interval, offset=offset)

    compare_quantities_single_run(problem, (TICDiag, AutogradTICDiag), schedule)


@pytest.mark.parametrize("problem", PROBLEMS, ids=PROBLEMS_IDS)
def test_tic_diag_separate_runs(problem):
    """Compare BackPACK and ``torch.autograd`` implementation of TICDiag.

    Both quantities run in separate cockpits.

    Args:
        problem (tests.utils.Problem): Settings for train loop.
    """
    interval, offset = 1, 2
    schedule = linear(interval, offset=offset)

    compare_quantities_separate_runs(problem, (TICDiag, AutogradTICDiag), schedule)


@pytest.mark.parametrize("problem", PROBLEMS, ids=PROBLEMS_IDS)
def test_tic_trace_single_run(problem):
    """Compare BackPACK and ``torch.autograd`` implementation of TICTrace.

    Both quantities run simultaneously in the same cockpit.

    Args:
        problem (tests.utils.Problem): Settings for train loop.
    """
    interval, offset = 1, 2
    schedule = linear(interval, offset=offset)

    compare_quantities_single_run(problem, (TICTrace, AutogradTICTrace), schedule)


@pytest.mark.parametrize("problem", PROBLEMS, ids=PROBLEMS_IDS)
def test_tic_trace_separate_runs(problem):
    """Compare BackPACK and ``torch.autograd`` implementation of TICTrace.

    Both quantities run in separate cockpits.

    Args:
        problem (tests.utils.Problem): Settings for train loop.
    """
    interval, offset = 1, 2
    schedule = linear(interval, offset=offset)

    compare_quantities_separate_runs(problem, (TICTrace, AutogradTICTrace), schedule)
