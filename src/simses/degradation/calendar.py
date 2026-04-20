from typing import Protocol

from simses.battery.state import BatteryState


class CalendarDegradation(Protocol):
    """Protocol for calendar aging models.

    Implementations are **stateless**: all accumulated values live in
    :class:`~simses.degradation.state.DegradationState` (owned by the
    :class:`~simses.degradation.degradation.DegradationModel`).  The current
    accumulated values are passed in on every call so that models using
    virtual-time continuation can compute the correct increments without
    maintaining their own internal state.
    """

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        """Compute incremental calendar capacity loss.

        Args:
            state: Current battery state.
            dt: Timestep in seconds.
            accumulated_qloss: Calendar capacity loss accumulated so far (p.u.,
                positive), used to seed virtual-time continuation.

        Returns:
            delta_qloss — positive increment in p.u. (capacity loss increases).
        """
        ...

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        """Compute incremental calendar resistance increase.

        Args:
            state: Current battery state.
            dt: Timestep in seconds.

        Returns:
            delta_soh_R — positive increment in p.u. (resistance increases).
        """
        ...
