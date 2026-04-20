"""Calendar degradation model for Molicel INR-18650-NMC cells.

Source: parameterised from accelerated-aging measurements adapted to the
same structure as the Naumann SonyLFP calendar law, with stress factors
bundled as 2-D lookup tables over (SOC, T). Ni Chuanqin (EES, TUM).
"""

import os

import pandas as pd

from simses.battery.state import BatteryState
from simses.degradation.calendar import CalendarDegradation
from simses.interpolation import interp2d_scalar

_SEC_PER_WEEK = 86400.0 * 7.0


def _load_stress_matrix(filename: str) -> tuple[list[float], list[float], list[list[float]]]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", filename)
    df = pd.read_csv(path)
    soc_lut = df["SOC"].tolist()
    T_lut = df["Temp"].dropna().tolist()
    mat = df.iloc[:, 2 : 2 + len(T_lut)].values.tolist()
    return soc_lut, T_lut, mat


class MolicelNMCCalendarDegradation(CalendarDegradation):
    """Calendar aging for Molicel INR-18650-NMC cells.

    Capacity loss follows a ``t^0.75`` power law with virtual-time
    continuation; resistance rise follows a ``sqrt(t)`` law with
    virtual-time continuation. Both stress factors are 2-D lookups over
    ``(SOC, T)`` valid in the range T ∈ [10, 50] °C and SOC ∈ [0, 1].
    Out-of-range inputs raise ``ValueError`` from the interpolation
    helper.

    This model is **stateless**: accumulated values are owned by the
    :class:`~simses.degradation.degradation.DegradationModel` and passed
    in on every call.
    """

    def __init__(self) -> None:
        self._soc_lut, self._T_lut, self._cap_mat = _load_stress_matrix("NMC_Molicel_capacity_cal.csv")
        _, _, self._ri_mat = _load_stress_matrix("NMC_Molicel_ri_cal.csv")

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        if dt == 0.0:
            return 0.0

        k_q = interp2d_scalar(state.soc, state.T, self._soc_lut, self._T_lut, self._cap_mat)
        if k_q <= 0.0:
            return 0.0

        dt_weeks = dt / _SEC_PER_WEEK
        virtual_weeks = (accumulated_qloss / k_q) ** (4.0 / 3.0)
        return k_q * (virtual_weeks + dt_weeks) ** 0.75 - accumulated_qloss

    def update_resistance(self, state: BatteryState, dt: float, accumulated_rinc: float) -> float:
        if dt == 0.0:
            return 0.0

        k_r = interp2d_scalar(state.soc, state.T, self._soc_lut, self._T_lut, self._ri_mat)
        if k_r <= 0.0:
            return 0.0

        dt_weeks = dt / _SEC_PER_WEEK
        virtual_weeks = (accumulated_rinc / k_r) ** 2
        return k_r * (virtual_weeks + dt_weeks) ** 0.5 - accumulated_rinc
