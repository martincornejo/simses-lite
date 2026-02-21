from abc import ABC, abstractmethod

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle


class CyclicDegradation(ABC):
    """Abstract base class for cyclic aging models.

    Implementations compute incremental capacity fade and resistance increase
    based on half-cycle stress factors (DOD, mean SOC, C-rate).
    """

    @abstractmethod
    def update(self, state: BatteryState, half_cycle: HalfCycle) -> tuple[float, float]:
        """Compute incremental cyclic degradation for a completed half-cycle.

        Args:
            state: Current battery state.
            half_cycle: Stress factors of the completed half-cycle.

        Returns:
            (delta_soh_Q, delta_soh_R) — incremental changes in p.u.
            delta_soh_Q is negative (capacity loss), delta_soh_R is positive
            (resistance increase).
        """
