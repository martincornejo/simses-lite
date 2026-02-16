from dataclasses import dataclass


@dataclass(slots=True)
class BatteryState:
    """
    Dataclass representing the state of a battery.

    v: float
        Terminal voltage of the battery in volts (V).
    i: float
        Current flowing into the battery in amperes (A). Positive for charging, negative for discharging.
    T: float
        Temperature of the battery in kelvin (K).
    power: float
        Power of the battery in watts (W).
    power_setpoint: float
        Desired power setpoint for the battery in watts (W).
    soc: float
        State of charge of the battery in per unit (p.u.).
    ocv: float
        Open-circuit voltage of the battery in volts (V).
    hys: float
        Hysteresis voltage of the battery in volts (V).
    rint: float
        Internal resistance of the battery in ohms (Ω).
    soh_Q: float
        State of health of the battery in terms of capacity in per unit (p.u.).
    soh_R: float
        State of health of the battery in terms of resistance in per unit (p.u.).
    is_charge: bool
        True if the battery is charging, False if discharging.
    loss: float
        Power loss of the battery in watts (W).
    """

    v: float  # V
    i: float  # A (positive if charging)
    T: float  # K
    power: float  # W
    power_setpoint: float  # W
    soc: float  # p.u.
    ocv: float  # V
    hys: float  # V
    rint: float  # ohm
    soh_Q: float  # p.u.
    soh_R: float  # p.u.
    is_charge: bool
    loss: float  # W
    # reversible heat
