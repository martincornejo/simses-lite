"""Calendar degradation model for Sony LFP cells.

Source: Naumann et al., "Analysis and modeling of calendar aging of a
commercial LiFePO4/graphite cell." Journal of Energy Storage (2018).
"""

import math

from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation

# Gas constant [J/(K*mol)]
R = 8.3144598
# Reference temperature [K]
T_REF = 298.15

# Capacity loss coefficients (sqrt(t) model)
K_REF_QLOSS = 1.2571e-05
EA_QLOSS = 17126.0
C_QLOSS = 2.8575
D_QLOSS = 0.60225

# Resistance increase coefficients (linear model)
K_REF_RINC = 3.4194e-10
EA_RINC = 71827.0
C_RINC = -3.3903
D_RINC = 1.5604


class SonyLFPCalendarDegradation(CalendarDegradation):
    """Calendar aging for Sony/Murata LFP cells (Naumann 2018).

    Capacity loss follows a sqrt(t) model with virtual time continuation.
    Resistance increase is linear in time.

    This model is **stateless**: accumulated values are owned by the
    :class:`~simses.degradation.degradation.DegradationModel` and passed in
    on every call.
    """

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        if dt == 0.0:
            return 0.0

        k_T_q = K_REF_QLOSS * math.exp(-EA_QLOSS / R * (1.0 / state.T - 1.0 / T_REF))
        k_soc_q = C_QLOSS * (state.soc - 0.5) ** 3 + D_QLOSS
        stress_q = k_T_q * k_soc_q

        if stress_q > 0.0:
            virtual_time = (accumulated_qloss / stress_q) ** 2
            delta_q = stress_q * math.sqrt(virtual_time + dt) - accumulated_qloss
        else:
            delta_q = 0.0

        return delta_q

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        if dt == 0.0:
            return 0.0

        k_T_r = K_REF_RINC * math.exp(-EA_RINC / R * (1.0 / state.T - 1.0 / T_REF))
        k_soc_r = C_RINC * (state.soc - 0.5) ** 2 + D_RINC
        return k_T_r * k_soc_r * dt
