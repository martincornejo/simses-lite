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

    This model is **stateless**: accumulated values are owned by the
    :class:`~simses.degradation.degradation.DegradationModel` and passed in
    on every call.
    """

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0

        k_crate_q = A_QLOSS * half_cycle.c_rate + B_QLOSS
        k_dod_q = C_QLOSS * (half_cycle.depth_of_discharge - 0.6) ** 3 + D_QLOSS
        stress_q = k_crate_q * k_dod_q

        if stress_q > 0.0:
            virtual_fec = (accumulated_qloss * 100.0 / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_fec + delta_fec) / 100.0 - accumulated_qloss
        else:
            delta_q = 0.0

        return delta_q

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle, accumulated_rinc: float) -> float:
        # accumulated_rinc is unused: this model is linear-in-FEC, no virtual-FEC needed.
        delta_fec = half_cycle.full_equivalent_cycles
        if delta_fec == 0.0:
            return 0.0

        k_crate_r = A_RINC * half_cycle.c_rate + B_RINC
        k_dod_r = C_RINC * (half_cycle.depth_of_discharge - 0.5) ** 3 + D_RINC
        return k_crate_r * k_dod_r * delta_fec / 100.0
