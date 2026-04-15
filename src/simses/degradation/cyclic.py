from typing import Protocol

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle


class CyclicDegradation(Protocol):
    """Protocol for cyclic aging models.

    Implementations are **stateless**: all accumulated values live in
    :class:`~simses.degradation.state.DegradationState` (owned by the
    :class:`~simses.degradation.degradation.DegradationModel`).  The current
    accumulated values are passed in on every call so that models using
    virtual-FEC continuation can compute the correct increments without
    maintaining their own internal state.
    """

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        """Compute incremental cyclic capacity loss for a completed half-cycle.

        Args:
            state: Current battery state.
            half_cycle: Stress factors of the completed half-cycle.
            accumulated_qloss: Cyclic capacity loss accumulated so far (p.u.,
                positive), used to seed virtual-FEC continuation.

        Returns:
            delta_qloss — positive increment in p.u. (capacity loss increases).
        """
        ...

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
        """Compute incremental cyclic resistance increase for a completed half-cycle.

        Args:
            state: Current battery state.
            half_cycle: Stress factors of the completed half-cycle.

        Returns:
            delta_soh_R — positive increment in p.u. (resistance increases).
        """
        ...
