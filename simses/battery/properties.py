from dataclasses import dataclass


@dataclass
class ElectricalCellProperties:
    """
    nominal_capacity :
        nominal capacity of one cell in Ah
    nominal_voltage :
        nominal voltage of one cell in V
    min_voltage :
        minimum allowed voltage of one cell in V
    max_voltage :
        maximum allowed voltage of one cell in V
    max_charge_rate :
        maximum allowed charge rate in 1/h (C-rate)
    max_discharge_rate :
        maximum allowed discharge rate in 1/h (C-rate)
    self_discharge_rate :
        self discharge rate in p.u. as X.X%-soc per day, e.g., 0.015 for 1.5% SOC loss per day
    coulomb_efficiency :
        coulomb efficiency of the cell in p.u.
    """

    nominal_capacity: float
    nominal_voltage: float
    min_voltage: float
    max_voltage: float
    max_charge_rate: float
    max_discharge_rate: float
    self_discharge_rate: float = 0.0
    coulomb_efficiency: float = 1.0


@dataclass
class ThermalCellProperties:
    """
    min_temperature :
        minimum allowed temperature for the cell in K
    max_temperature :
        maximum allowed temperature for the cell in K
    mass :
        mass of one cell in kg
    specific_heat :
        specific heat of the cell in J/kgK
    convection_coeffecient :
        convection coefficient in W/m2K
    """

    min_temperature: float
    max_temperature: float
    mass: float
    specific_heat: float
    convection_coefficient: float
