import os

import numpy as np
import pandas as pd

from simses.interpolation import interp1d_scalar


class SinamicsS120:
    """Siemens Sinamics S120 converter loss model from measured efficiency curves.

    Lookup-table model built from a CSV of measured efficiency values for
    charging (AC→DC) and discharging (DC→AC) at 101 normalised power points.
    All power arguments are in per-unit of the converter's rated max power.

    The CSV carries separate ``Charging`` and ``Discharging`` curves; in the
    bundled measurement data they differ by a mean of 0.23% and a maximum of
    0.40% (the discharging curve is systematically ~0.2 efficiency-points
    higher).

    Source: Schimpe et al., "Energy efficiency evaluation of grid
    connection scenarios for stationary battery energy storage systems",
    Energy Procedia 155 (2018) 77–101, doi:10.1016/j.egypro.2018.11.065.
    """

    def __init__(self, use_discharging_curve: bool = False) -> None:
        """
        Args:
            use_discharging_curve: If ``True``, use the measured
                ``Discharging`` column for the discharge branch. If
                ``False`` (default), use the ``Charging`` column for both
                directions — keeps the model strictly symmetric about zero
                power. Set to ``True`` to preserve the measured
                charge/discharge asymmetry.
        """
        path = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(path, "data", "sinamics_S120_efficiency.csv")
        df_eff = pd.read_csv(file)  # efficiency curves

        eff_ch = df_eff["Charging"][::10]  # every 10th row of the 1001-row table
        eff_dch = df_eff["Discharging"][::10] if use_discharging_curve else eff_ch

        input_ch = np.linspace(0, 1, 101)
        output_ch = input_ch * eff_ch

        input_dch = np.linspace(0, 1, 101)
        output_dch = input_dch / eff_dch

        self._inp = np.hstack((-input_dch[1:][::-1], 0, input_ch[1:])).tolist()
        self._out = np.hstack((-output_dch[1:][::-1], 0, output_ch[1:])).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)


class SinamicsS120Fit:
    """Siemens Sinamics S120 converter loss model from a parametric fit.

    Symmetric loss model of the form
    ``loss(p) = k0 × (1 − exp(−m0·|p|)) + k1·|p| + k2·|p|²``
    where ``p`` is normalised power (p.u. of the converter's rated max
    power). The coefficients are a least-squares fit to the same
    measurement data used by :class:`SinamicsS120`. At construction the
    fit is sampled at 101 points and interpolated at runtime — so the
    evaluation cost matches :class:`SinamicsS120`; the two variants
    differ only in how their interpolation points are generated
    (parametric fit vs measured CSV).

    Source: Schimpe et al., "Energy efficiency evaluation of grid
    connection scenarios for stationary battery energy storage systems",
    Energy Procedia 155 (2018) 77–101, doi:10.1016/j.egypro.2018.11.065.
    """

    def __init__(self) -> None:
        # self.params = {"k0": 0.00601144, "k1": 0.00863612, "k2": 0.01195589, "m0": 97}
        params = (0.00601144, 0.00863612, 0.01195589, 97)
        k0, k1, k2, m0 = params

        def loss(power):
            power_factor = np.abs(power)
            return (
                k0 * (1 - np.exp(-m0 * power_factor))  # constant loss + activation
                + k1 * power_factor
                + k2 * power_factor**2
            )

        input_ch = np.linspace(0, 1, 101)
        output_ch = input_ch - loss(input_ch)

        input_dch = -np.linspace(0, 1, 101)
        output_dch = input_dch - loss(input_dch)

        self._inp = np.hstack((input_dch[1:][::-1], 0, input_ch[1:])).tolist()
        self._out = np.hstack((output_dch[1:][::-1], 0, output_ch[1:])).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._inp, self._out)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._out, self._inp)
