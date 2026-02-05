import os

import numpy as np
import pandas as pd


class SinamicsS120:
    def __init__(self) -> None:
        super().__init__()
        path = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(path, "data", "sinamics_S120_efficiency.csv")
        df_eff = pd.read_csv(file)  # efficiency curves

        # create lookup tables for input/ouput power conversion
        # only use charging data for both charging and discharging
        input_ch = np.linspace(0, 1, 101)
        output_ch = input_ch * df_eff["Charging"][::10]  # take every 10 item of the lookup table

        input_dch = np.linspace(0, 1, 101)
        # output_dch = input_dch / df_eff["Discharging"][::10]  # take every 10 item of the lookup table
        output_dch = input_dch / df_eff["Charging"][::10]  # take every 10 item of the lookup table

        self._inp = np.hstack((-input_dch[1:][::-1], 0, input_ch[1:]))
        self._out = np.hstack((-output_dch[1:][::-1], 0, output_ch[1:]))

    def ac_to_dc(self, power_ac: float) -> float:
        return float(np.interp(power_ac, self._inp, self._out))

    def dc_to_ac(self, power_dc: float) -> float:
        return float(np.interp(power_dc, self._out, self._inp))


class SinamicsS120Fit:
    def __init__(self) -> None:
        super().__init__()
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

        self._inp = np.hstack((input_dch[1:][::-1], 0, input_ch[1:]))
        self._out = np.hstack((output_dch[1:][::-1], 0, output_ch[1:]))

    def ac_to_dc(self, power_ac: float) -> float:
        return float(np.interp(power_ac, self._inp, self._out))

    def dc_to_ac(self, power_dc: float) -> float:
        return float(np.interp(power_dc, self._out, self._inp))
