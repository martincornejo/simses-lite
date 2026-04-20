"""Cyclic degradation model for Molicel INR-18650-NMC cells.

Source: parameterised from accelerated-aging measurements adapted to the
same structure as the Naumann SonyLFP cyclic law, with stress factors
bundled as 1-D lookup tables over DoD. Ni Chuanqin (EES, TUM).
"""

import os

import pandas as pd

from simses.battery.state import BatteryState
from simses.degradation.cycle_detector import HalfCycle
from simses.degradation.cyclic import CyclicDegradation
from simses.interpolation import interp1d_scalar

# Nominal single-cell capacity (Ah). The legacy cyclic law uses charge
# throughput in Ah as its independent variable; we reconstruct it from
# the half-cycle's depth-of-discharge.
_NOMINAL_CAPACITY_AH = 1.9

# Power-law exponents (dimensionless).
_EXPONENT_QLOSS = 0.5562
_EXPONENT_RINC = 0.5562


def _load_1d_stress(filename: str, column: str) -> tuple[list[float], list[float]]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", filename)
    df = pd.read_csv(path)
    return df["DOD"].tolist(), df[column].tolist()


class MolicelNMCCyclicDegradation(CyclicDegradation):
    """Cyclic aging for Molicel INR-18650-NMC cells.

    Capacity loss follows a power law in charge throughput ``Q^0.5562``
    with virtual-throughput continuation; resistance rise follows the
    same power law. The stress factors are 1-D lookups over DoD. Charge
    throughput per half-cycle is reconstructed as ``DoD * 1.9 Ah`` using
    the Molicel's nominal cell capacity.

    The legacy model also includes an asymmetric C-rate scaling
    (separate coefficients above 0.5 C for charge vs discharge). That
    branching requires charge/discharge direction on the
    :class:`HalfCycle`, which the simses-lite detector does not expose;
    the scaling is therefore omitted here. DoD is the dominant stress
    factor and is preserved.

    This model is **stateless**: accumulated values are owned by the
    :class:`~simses.degradation.degradation.DegradationModel` and passed
    in on every call.
    """

    def __init__(self) -> None:
        self._dod_lut_cap, self._cap_stress = _load_1d_stress("NMC_Molicel_capacity_cyc.csv", "f_capacity_cyc")
        self._dod_lut_ri, self._ri_stress = _load_1d_stress("NMC_Molicel_ri_cyc.csv", "f_ri_cyc")

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        dod = half_cycle.depth_of_discharge
        if dod == 0.0:
            return 0.0

        k_q = interp1d_scalar(dod, self._dod_lut_cap, self._cap_stress)
        if k_q <= 0.0:
            return 0.0

        throughput_ah = dod * _NOMINAL_CAPACITY_AH
        virtual_q = (accumulated_qloss / k_q) ** (1.0 / _EXPONENT_QLOSS)
        return max(0.0, k_q * (virtual_q + throughput_ah) ** _EXPONENT_QLOSS - accumulated_qloss)

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle, accumulated_rinc: float) -> float:
        dod = half_cycle.depth_of_discharge
        if dod == 0.0:
            return 0.0

        k_r = interp1d_scalar(dod, self._dod_lut_ri, self._ri_stress)
        if k_r <= 0.0:
            return 0.0

        throughput_ah = dod * _NOMINAL_CAPACITY_AH
        virtual_q = (accumulated_rinc / k_r) ** (1.0 / _EXPONENT_RINC)
        return max(0.0, k_r * (virtual_q + throughput_ah) ** _EXPONENT_RINC - accumulated_rinc)
