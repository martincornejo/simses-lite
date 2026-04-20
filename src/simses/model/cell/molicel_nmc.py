import math
import os

import pandas as pd

from simses.battery.battery import BatteryState, CellType
from simses.battery.format import RoundCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties
from simses.interpolation import interp1d_scalar


class MolicelNMC(CellType):
    """Molicel INR-18650-NMC cylindrical NMC cell.

    Nickel-manganese-cobalt oxide cell, 1.9 Ah nominal capacity, 3.7 V
    nominal voltage. Analytical ``OCV(SOC)`` as a sum of sigmoids and a
    linear term; internal resistance is a 1-D lookup in SOC (the source
    characterisation is symmetric for charge and discharge and
    temperature-independent in the tested range).

    Source: Schuster, S. F., Bach, T., Fleder, E., Müller, J., Brand, M.,
    Sextl, G., & Jossen, A. (2015). *Nonlinear aging characteristics of
    lithium-ion cells under different operational conditions.* Journal of
    Energy Storage, 1, 44–53, doi:10.1016/j.est.2015.05.003.
    """

    def __init__(self) -> None:
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=1.9,  # Ah
                nominal_voltage=3.7,  # V
                max_voltage=4.25,  # V
                min_voltage=3.0,  # V
                max_charge_rate=1.05,  # 1/h
                max_discharge_rate=2.1,  # 1/h
                self_discharge_rate=0.0,
                coulomb_efficiency=1.0,  # p.u.
            ),
            thermal=ThermalCellProperties(
                min_temperature=0.0,  # °C
                max_temperature=45.0,  # °C
                mass=0.045,  # kg per cell
                specific_heat=965,  # J/kgK
                convection_coefficient=15,  # W/m2K
            ),
            cell_format=RoundCell(diameter=18, length=65),
        )
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        df_rint = pd.read_csv(os.path.join(path, "NMC_Molicel_Rint.csv"))
        self._rint_lut_soc = df_rint["SOC"].tolist()
        self._rint_lut_rint = df_rint["Rint"].tolist()

    def open_circuit_voltage(self, state: BatteryState) -> float:
        a1 = -1.6206
        a2 = -6.9895
        a3 = 1.4458
        a4 = 1.9530
        b1 = 3.4206
        b2 = 0.8759
        k0 = 2.0127
        k1 = 2.7684
        k2 = 1.0698
        k3 = 4.1431
        k4 = -3.8417
        k5 = -0.1856

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
        return interp1d_scalar(state.soc, self._rint_lut_soc, self._rint_lut_rint)
