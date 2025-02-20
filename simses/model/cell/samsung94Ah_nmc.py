import math

from simses.battery.battery import BatteryState
from simses.battery.cell import CellType
from simses.battery.format import PrismaticCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties


class Samsung94AhNMC(CellType):
    def __init__(self) -> None:
        super().__init__(
            electrical=ElectricalCellProperties(
                nominal_capacity=94.0,  # Ah
                nominal_voltage=3.68,  # V
                max_voltage=4.15,  # V
                min_voltage=2.7,  # V
                max_charge_rate=2.0,  # 1/h
                max_discharge_rate=2.0,  # 1/h
                self_discharge_rate=0.0 / (365 / 12),
                coulomb_efficiency=1.0,  # p.u.
            ),
            thermal=ThermalCellProperties(
                min_temperature=233.15,  # K
                max_temperature=333.15,  # K
                mass=2.1,  # kg per cell
                specific_heat=1000,  # J/kgK
                convection_coefficient=15,  # W/m2K
            ),
            cell_format=PrismaticCell(
                height=125,  # mm
                width=45.0,  # mm
                length=173.0,  # mm
            ),
        )

    def open_circuit_voltage(self, state: BatteryState) -> float:
        a1 = 3.3479
        a2 = -6.7241
        a3 = 2.5958
        a4 = -61.9684
        b1 = 0.6350
        b2 = 1.4376
        k0 = 4.5868
        k1 = 3.1768
        k2 = -3.8418
        k3 = -4.6932
        k4 = 0.3618
        k5 = 0.9949

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
        return 0.75e-3
