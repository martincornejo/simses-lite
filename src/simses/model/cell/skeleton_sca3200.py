import math

from simses.battery.battery import BatteryState
from simses.battery.cell import CellType
from simses.battery.format import RoundCell
from simses.battery.properties import ElectricalCellProperties, ThermalCellProperties


class SCA3200(CellType):
    def __init__(
            self,
            capacitance:float = 3200.0,  # F
            rated_voltage:float = 2.85,  # V
            min_voltage=1.425,  # V
            nom_voltage=2.0,  # V
            internal_resistance:float = 0.18e-3,  # Ohm
            leakage_current=11e-3,  # A
            peak_power = 11.3e3,  # W
            diameter:float = 60.2,  # mm
            length:float = 138.0, # mm
            mass:float = 0.53,  # kg
            t_min:float = -40.0,  # °C
            t_max:float = 65.0,  # °C
            thermal_cap = 633.7,  # J/°C
    ) -> None:

        energy_wh = (rated_voltage**2 - min_voltage**2) * capacitance / 2 / 3600

        # leakage current seems to be unused at the moment
        if leakage_current == 0.0:
            leakage_pu = 0.0
        else:
            tau_leak = (rated_voltage / leakage_current) * capacitance
            delta_1d = 1 - math.e**(24 * 3600 / tau_leak)
            usable_range = (rated_voltage - min_voltage) / rated_voltage
            leakage_pu = (usable_range - delta_1d) / usable_range

        c_rate = peak_power/energy_wh  # very basic approximation

        electrical = ElectricalCellProperties(
            nominal_capacity=energy_wh/nom_voltage,
            nominal_voltage=nom_voltage,
            max_voltage=rated_voltage,
            min_voltage=min_voltage,
            max_charge_rate=c_rate,
            max_discharge_rate=c_rate,
            self_discharge_rate=leakage_pu,
            coulomb_efficiency=1.0,
        )

        thermal = ThermalCellProperties(
            min_temperature=t_min,
            max_temperature=t_max,
            mass=mass,
            specific_heat=thermal_cap/mass,
            convection_coefficient=15,  # W/m2K (placeholder value)
        )

        cell_format = RoundCell(diameter, length)

        super().__init__(
            electrical=electrical,
            thermal=thermal,
            cell_format=cell_format,
        )

        self.r_int = internal_resistance

    def open_circuit_voltage(self, state: BatteryState) -> float:
        return self.electrical.min_voltage + (self.electrical.max_voltage - self.electrical.min_voltage) * state.soc

    def internal_resistance(self, state: BatteryState) -> float:
        return self.r_int
