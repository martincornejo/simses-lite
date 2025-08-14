from dataclasses import dataclass


@dataclass(slots=True)
class BatteryState:
    v: float  # V
    i: float  # A
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
    loss: float  # in W
    # reversible heat
