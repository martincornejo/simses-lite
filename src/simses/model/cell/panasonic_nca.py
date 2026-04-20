import math
import os

import pandas as pd

from simses.battery.battery import BatteryState, CellType
from simses.battery.format import RoundCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.interpolation import interp1d_scalar


class PanasonicNCA(CellType):
    """Panasonic NCR18650 cylindrical NCA cell.

    Nickel-cobalt-aluminum oxide cell, 2.73 Ah nominal capacity, 3.6 V
    nominal voltage, conservative 0.5 C charge / 3.5 C discharge. Analytical
    ``OCV(SOC)`` as a sum of sigmoids and a linear term; internal resistance
    is a 1-D lookup in SOC with separate charge and discharge curves.

    Source: P. Keil, S. F. Schuster, J. Wilhelm, J. Travi, A. Hauser,
    R. C. Karl, A. Jossen. *Calendar aging of lithium-ion batteries.*
    Journal of The Electrochemical Society 163(9) (2016) A1872-A1880,
    doi:10.1149/2.0411609jes.
    """

    def __init__(self) -> None:
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=2.73,  # Ah
                nominal_voltage=3.6,  # V
                max_voltage=4.2,  # V
                min_voltage=2.5,  # V
                max_charge_rate=0.5,  # 1/h
                max_discharge_rate=3.5,  # 1/h
                self_discharge_rate=0.0,
                coulomb_efficiency=1.0,  # p.u.
            ),
            thermal=ThermalCellProperties(
                min_temperature=0.0,  # °C
                max_temperature=45.0,  # °C
                mass=0.044,  # kg per cell
                specific_heat=1048,  # J/kgK
                convection_coefficient=15,  # W/m2K
            ),
            cell_format=RoundCell(diameter=18, length=65),
        )
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        df_rint = pd.read_csv(os.path.join(path, "NCA_PanasonicNCR_Rint.csv"))
        self._rint_lut_soc = df_rint["SOC"].tolist()
        self._rint_lut_ch = df_rint["R_ch"].tolist()
        self._rint_lut_dch = df_rint["R_dch"].tolist()

    def open_circuit_voltage(self, state: BatteryState) -> float:
        a1 = -0.3777
        a2 = 10.2859
        a3 = 17.0608
        a4 = -3.7820
        b1 = -5.6272
        b2 = 0.2907
        k0 = 4.9852
        k1 = -2.86523
        k2 = 0.3852
        k3 = -0.1599
        k4 = 1.2256
        k5 = 0.7412

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
        lut = self._rint_lut_ch if state.is_charge else self._rint_lut_dch
        return interp1d_scalar(state.soc, self._rint_lut_soc, lut)
