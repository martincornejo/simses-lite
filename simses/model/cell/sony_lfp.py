import math
import os

import numpy as np
import pandas as pd
from scipy.interpolate import RegularGridInterpolator

from simses.battery.battery import BatteryState, CellType
from simses.battery.format import RoundCell26650
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.degradation import DegradationModel
from simses.model.degradation.sony_lfp_calendar import SonyLFPCalendarDegradation
from simses.model.degradation.sony_lfp_cyclic import SonyLFPCyclicDegradation


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
        path = os.path.dirname(os.path.abspath(__file__))

        ## OCV look-up table
        file_ocv = os.path.join(path, "data", "CLFP_Sony_US26650_OCV.csv")
        df_ocv = pd.read_csv(file_ocv)
        self._ocv_lut_soc = df_ocv["SOC"].to_numpy()
        self._ocv_lut_ocv = df_ocv["OCV"].to_numpy()

        ## Hystheresis look-up table
        file_hyst = os.path.join(path, "data", "CLFP_Sony_US26650_HystV.csv")
        df_hyst = pd.read_csv(file_hyst)
        self._hyst_lut_soc = df_hyst["SOC"].to_numpy()
        self._hyst_lut_hyst = df_hyst["HystV"].to_numpy()

        # entropic coefficient look-up table
        file_entropy = os.path.join(path, "data", "CLFP_Sony_US26650_entropy.csv")
        df_entropy = pd.read_csv(file_entropy)
        self._entropy_lut_soc = df_entropy["SOC"].to_numpy()
        self._entropy_lut_entropy = df_entropy["S"].to_numpy()

        ## internal resistance 2D look-up table
        file_rint = os.path.join(path, "data", "CLFP_Sony_US26650_Rint.csv")
        df_rint = pd.read_csv(file_rint)

        soc_rint = df_rint["SOC"]
        T_rint = df_rint["Temp"].dropna()

        rint_mat_ch = np.array(df_rint.iloc[:, 2:6])
        rint_mat_dch = np.array(df_rint.iloc[:, 6:])

        self._rint_ch_interp2d = RegularGridInterpolator((soc_rint, T_rint), np.array(rint_mat_ch))
        self._rint_dch_interp2d = RegularGridInterpolator((soc_rint, T_rint), np.array(rint_mat_dch))

    def open_circuit_voltage(self, state: BatteryState) -> float:
        soc = state.soc
        return float(np.interp(soc, self._ocv_lut_soc, self._ocv_lut_ocv))

    def hystheresis_voltage(self, state):
        soc = state.soc
        return float(np.interp(soc, self._hyst_lut_soc, self._hyst_lut_hyst))

    def entropic_coefficient(self, state: BatteryState) -> float:
        soc = state.soc
        return float(np.interp(soc, self._entropy_lut_soc, self._entropy_lut_entropy))

    def internal_resistance(self, state: BatteryState) -> float:
        if state.is_charge:
            rint = self._rint_ch_interp2d((state.soc, state.T))
        else:
            rint = self._rint_dch_interp2d((state.soc, state.T))
        return float(rint)

    def default_degradation_model(self, initial_soc: float) -> DegradationModel:
        return DegradationModel(
            cyclic=SonyLFPCyclicDegradation(),
            calendar=SonyLFPCalendarDegradation(),
            initial_soc=initial_soc,
        )
