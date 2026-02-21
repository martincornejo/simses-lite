"""Cyclic degradation model for Sony LFP cells.

Source: Naumann et al., "Analysis and modeling of cycle aging of a
commercial LiFePO4/graphite cell." Journal of Power Sources (2020).
"""

import math

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle
from simses.degradation.cyclic import CyclicDegradation

# Capacity loss coefficients (sqrt(FEC) model)
A_QLOSS = 0.0630
B_QLOSS = 0.0971
C_QLOSS = 4.0253
D_QLOSS = 1.0923

# Resistance increase coefficients (linear in FEC)
A_RINC = -0.0020
B_RINC = 0.0021
C_RINC = 6.8477
D_RINC = 0.9182


class SonyLFPCyclicDegradation(CyclicDegradation):
    """Cyclic aging for Sony/Murata LFP cells (Naumann 2020).

    Capacity loss follows a sqrt(FEC) model with virtual FEC continuation.
    Resistance increase is linear in FEC.
    """

    def __init__(self) -> None:
        self._accumulated_qloss: float = 0.0  # cumulative capacity loss in p.u.
        self._accumulated_rinc: float = 0.0  # cumulative resistance increase in p.u.

    def update(self, state: BatteryState, half_cycle: HalfCycle) -> tuple[float, float]:
        dod = half_cycle.depth_of_discharge
        crate = half_cycle.c_rate
        delta_fec = half_cycle.full_equivalent_cycles

        if delta_fec == 0.0:
            return 0.0, 0.0

        # --- Capacity loss (sqrt(FEC) with virtual FEC) ---
        k_crate_q = A_QLOSS * crate + B_QLOSS
        k_dod_q = C_QLOSS * (dod - 0.6) ** 3 + D_QLOSS

        stress_q = k_crate_q * k_dod_q
        if stress_q > 0.0:
            virtual_fec = (self._accumulated_qloss * 100.0 / stress_q) ** 2
            new_total_qloss = stress_q * math.sqrt(virtual_fec + delta_fec) / 100.0
            delta_q = new_total_qloss - self._accumulated_qloss
        else:
            delta_q = 0.0

        self._accumulated_qloss += delta_q

        # --- Resistance increase (linear in FEC) ---
        k_crate_r = A_RINC * crate + B_RINC
        k_dod_r = C_RINC * (dod - 0.5) ** 3 + D_RINC
        delta_r = k_crate_r * k_dod_r * delta_fec / 100.0

        self._accumulated_rinc += delta_r

        return -delta_q, delta_r
