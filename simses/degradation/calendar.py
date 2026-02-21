from abc import ABC, abstractmethod

from simses.battery.state import BatteryState


class CalendarDegradation(ABC):
    """Abstract base class for calendar aging models.

    Implementations compute incremental capacity fade and resistance increase
    based on time, temperature, and SOC.
    """

    @abstractmethod
    def update(self, state: BatteryState, dt: float) -> tuple[float, float]:
        """Compute incremental calendar degradation.

        Args:
            state: Current battery state.
            dt: Timestep in seconds.

        Returns:
            (delta_soh_Q, delta_soh_R) — incremental changes in p.u.
            delta_soh_Q is negative (capacity loss), delta_soh_R is positive
            (resistance increase).
        """
