import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from simses.battery.battery import BatteryState
from simses.battery.cell import CellType
from simses.battery.format import RoundCell26650
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties


class SonyLFP(CellType):
    """
    Source SONY_US26650FTC1_Product Specification and Naumann, Maik. Techno-economic evaluation of stationary
    lithium_ion energy storage systems with special consideration of aging.
    PhD Thesis. Technical University Munich, 2018.
    """

    def __init__(self):
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=3.0,  # Ah
                nominal_voltage=3.2,  # V
                max_voltage=3.6,  # V
                min_voltage=2.0,  # V
                max_charge_rate=1.0,  # 1/h
                max_discharge_rate=6.6,  # 1/h
                self_discharge_rate=0.0 / (365 / 12),
                coulomb_efficiency=1.0,  # p.u.
            ),
            thermal=ThermalCellProperties(
                min_temperature=273.15,  # K
                max_temperature=333.15,  # K
                mass=0.07,  # kg per cell
                specific_heat=1001,  # J/kgK
                convection_coefficient=15,  # W/m2K
            ),
            cell_format=RoundCell26650(),
        )
        # path, _ = os.path.split(os.path.abspath(__file__))
        # path = Path(path)
        path = "simses/model/cell/data/"

        ## internal resistance 2D look-up table
        file = os.path.join(path, "CLFP_Sony_US26650_Rint.csv")
        df_rint = pd.read_csv(file)

        soc_rint = df_rint["SOC"]
        T_rint = df_rint["Temp"].dropna()

        rint_mat_ch = np.array(df_rint.iloc[:, 2:6])
        rint_mat_dch = np.array(df_rint.iloc[:, 6:])

        self._rint_ch_interp2d = RegularGridInterpolator((soc_rint, T_rint), np.array(rint_mat_ch))
        self._rint_dch_interp2d = RegularGridInterpolator((soc_rint, T_rint), np.array(rint_mat_dch))

    def open_circuit_voltage(self, state: BatteryState) -> float:
        """Parameters build with ocv fitting"""
        a1 = -116.2064
        a2 = -22.4512
        a3 = 358.9072
        a4 = 499.9994
        b1 = -0.1572
        b2 = -0.0944
        k0 = 2.0020
        k1 = -3.3160
        k2 = 4.9996
        k3 = -0.4574
        k4 = -1.3646
        k5 = 0.1251

        soc = state.soc

        ocv = (
            k0
            + k1 / (1 + math.exp(a1 * (soc - b1)))
            + k2 / (1 + math.exp(a2 * (soc - b2)))
            + k3 / (1 + math.exp(a3 * (soc - 1)))
            + k4 / (1 + math.exp(a4 * soc))
            + k5 * soc
        )

        return ocv

    def internal_resistance(self, state: BatteryState) -> float:
        if state.is_charge:
            rint = self._rint_ch_interp2d((state.soc, state.T))
        else:
            rint = self._rint_dch_interp2d((state.soc, state.T))
        return float(rint)
