import os
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import make_interp_spline

# TODO make a subclass system
# from simses.converter.converter import Converter


@dataclass(slots=True)
class ConverterState:
    power_setpoint: float = 0.0
    power: float = 0.0
    loss: float = 0.0


class SinamicsS120:
    def __init__(self, max_power: float, storage) -> None:
        super().__init__()
        self.max_power = max_power
        self.storage = storage
        self.state = ConverterState()

        path = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(path, "data", "sinamics_S120_efficiency.csv")
        df_eff = pd.read_csv(file)  # efficiency curves

        # create lookup tables for input/ouput power conversion
        # only use charging data for both charging and discharging
        input_ch = max_power * np.linspace(0, 1, 101)
        output_ch = input_ch * df_eff["Charging"][::10]  # take every 10 item of the lookup table

        input_dch = max_power * np.linspace(0, 1, 101)
        # output_dch = input_dch / df_eff["Discharging"][::10]  # take every 10 item of the lookup table
        output_dch = input_dch / df_eff["Charging"][::10]  # take every 10 item of the lookup table

        inp = np.hstack((-input_dch[1:][::-1], 0, input_ch[1:]))
        out = np.hstack((-output_dch[1:][::-1], 0, output_ch[1:]))

        self.ac_to_dc = make_interp_spline(inp, out, k=1)
        self.dc_to_ac = make_interp_spline(out, inp, k=1)

    def update(self, power_setpoint, dt):
        max_power = self.max_power
        power_ac = max(-max_power, min(power_setpoint, max_power))
        power_dc = float(self.ac_to_dc(power_ac))

        self.storage.update(power_dc, dt)
        power_storage = self.storage.state.power

        # check if subsystem fullfilled DC power
        # if not, re-calculate required AC power
        if power_dc != 0 and (abs(power_dc - power_storage) / abs(power_dc)) > 0.01:  # 1% difference tolerance
            power_dc = power_storage
            power_ac = float(self.dc_to_ac(power_dc))

        # calculate conversion losses
        loss = power_ac - power_dc

        # update state
        self.state.power_setpoint = power_setpoint
        self.state.power = power_ac
        self.state.loss = loss


class SinamicsS120Fit:
    def __init__(self, max_power: float, storage) -> None:
        super().__init__()
        self.max_power = max_power
        self.storage = storage
        self.state = ConverterState()

        # self.params = {"k0": 0.00601144, "k1": 0.00863612, "k2": 0.01195589, "m0": 97}
        params = (0.00601144, 0.00863612, 0.01195589, 97)
        k0, k1, k2, m0 = params

        def loss(power):
            power_factor = np.abs(power) / max_power
            return (
                k0 * (1 - np.exp(-m0 * power_factor))  # constant loss + activation
                + k1 * power_factor
                + k2 * power_factor**2
            ) * max_power

        input_ch = max_power * np.linspace(0, 1, 101)
        output_ch = input_ch - loss(input_ch)

        input_dch = -max_power * np.linspace(0, 1, 101)
        output_dch = input_dch - loss(input_dch)

        inp = np.hstack((input_dch[1:][::-1], 0, input_ch[1:]))
        out = np.hstack((output_dch[1:][::-1], 0, output_ch[1:]))

        self.ac_to_dc = make_interp_spline(inp, out, k=1)
        self.dc_to_ac = make_interp_spline(out, inp, k=1)

    def update(self, power_setpoint, dt):
        max_power = self.max_power
        power_ac = max(-max_power, min(power_setpoint, max_power))
        power_dc = float(self.ac_to_dc(power_ac))

        self.storage.update(power_dc, dt)
        power_storage = self.storage.state.power

        # check if subsystem fullfilled DC power
        # if not, re-calculate required AC power
        if power_dc != 0 and (abs(power_dc - power_storage) / abs(power_dc)) > 0.01:  # 1% difference tolerance
            power_dc = power_storage
            power_ac = float(self.dc_to_ac(power_dc))

        # calculate conversion losses
        loss = power_ac - power_dc

        # update state
        self.state.power_setpoint = power_setpoint
        self.state.power = power_ac
        self.state.loss = loss
