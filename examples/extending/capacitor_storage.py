"""Non-battery storage: a lumped supercapacitor.

Demonstrates how to plug a storage that is *not* a :class:`Battery` into
the simses subsystems. The required contract is deliberately small:

* For :class:`~simses.converter.converter.Converter`: a ``step(power, dt)``
  method and a ``state.power`` attribute. That's it.
* For :class:`~simses.thermal.AmbientThermalModel` or
  :class:`~simses.thermal.ContainerThermalModel`: additionally expose
  ``state.T``, ``state.heat``, ``thermal_capacity``, and
  ``thermal_resistance`` — the :class:`~simses.thermal.protocol.ThermalComponent`
  protocol.

What you do **not** get for free:

* **Degradation** — the :class:`~simses.degradation.degradation.DegradationModel`
  assumes battery-specific fields (``soh_Q``, ``soh_R``) and is wired in
  by :class:`Battery`. Supercap aging would need its own tracking.
* **Derating** — :class:`~simses.battery.derating.CurrentDerating` reads
  battery state (SOC, voltage window, max charge current). You'd build
  supercap-specific derating yourself if needed.

The lumped model used below represents a capacitor bank with capacitance
``C`` and equivalent series resistance (ESR) ``R_s``. Terminal voltage is
``V_term = V_cap + R_s · i``, power at the terminals is ``P = V_term · i``
— the same quadratic form :class:`Battery` solves for its ECM.
"""

import math
from dataclasses import dataclass

import pandas as pd

from simses.converter import Converter
from simses.model.converter.fix_efficiency import FixedEfficiency
from simses.thermal import AmbientThermalModel


@dataclass
class CapacitorState:
    """Mutable state of a :class:`Capacitor`.

    Attributes:
        Q:               Stored charge in C.
        V_cap:           Voltage across the ideal capacitor element in V.
        v:               Terminal voltage in V (``V_cap + R_s · i``).
        i:               Current in A (positive = charging).
        power:           Delivered power at terminals in W.
        power_setpoint:  Requested power in W.
        loss:            Ohmic loss across the ESR in W (``R_s · i²``, ≥ 0).
        heat:            Internal heat generation in W — equals ``loss``
                         for this purely-ohmic model.
        T:               Lumped temperature in °C (written by a thermal
                         model if registered, otherwise unchanged).
    """

    Q: float
    V_cap: float
    v: float = 0.0
    i: float = 0.0
    power: float = 0.0
    power_setpoint: float = 0.0
    loss: float = 0.0
    heat: float = 0.0
    T: float = 25.0


class Capacitor:
    """Lumped capacitor storage with ESR, lossy but otherwise ideal.

    Equation: ``V_term = Q / C + R_s · i``, with ``P = V_term · i``
    solved for ``i`` at every step (same quadratic as the battery ECM).

    Satisfies the storage contract required by
    :class:`~simses.converter.converter.Converter` and the
    :class:`~simses.thermal.protocol.ThermalComponent` protocol so it
    can also be registered with a thermal model.
    """

    def __init__(
        self,
        capacitance: float,
        esr: float,
        initial_voltage: float,
        *,
        mass: float = 1.0,
        specific_heat: float = 1000.0,
        thermal_resistance: float = 1.0,
        initial_T: float = 25.0,
    ) -> None:
        """
        Args:
            capacitance: Capacitance in F.
            esr: Equivalent series resistance in Ω.
            initial_voltage: Starting ``V_cap`` in V.
            mass: Lumped mass in kg (used for thermal capacity).
            specific_heat: Specific heat capacity in J/kgK.
            thermal_resistance: Thermal resistance to ambient in K/W.
            initial_T: Starting temperature in °C.
        """
        self.capacitance = capacitance
        self.esr = esr
        self.mass = mass
        self.specific_heat = specific_heat
        self.thermal_resistance = thermal_resistance
        self.state = CapacitorState(
            Q=capacitance * initial_voltage,
            V_cap=initial_voltage,
            T=initial_T,
        )

    @property
    def thermal_capacity(self) -> float:
        """Thermal capacity in J/K, computed from ``mass × specific_heat``."""
        return self.mass * self.specific_heat

    def step(self, power_setpoint: float, dt: float) -> None:
        """Advance the capacitor state by one timestep.

        Args:
            power_setpoint: Requested power at terminals in W
                (positive = charging, negative = discharging).
            dt: Timestep in seconds.
        """
        V_cap = self.state.V_cap
        R_s = self.esr

        # Solve P = (V_cap + R_s · i) · i for i — same quadratic form as
        # the ECM in Battery, with V_cap playing the role of OCV.
        if power_setpoint == 0.0:
            i = 0.0
        else:
            discriminant = V_cap**2 + 4.0 * R_s * power_setpoint
            i = (-V_cap + math.sqrt(max(0.0, discriminant))) / (2.0 * R_s)

        # Integrate charge; update cap voltage from the new charge.
        self.state.Q += i * dt
        self.state.V_cap = self.state.Q / self.capacitance

        v_term = V_cap + R_s * i
        heat = R_s * i**2

        self.state.i = i
        self.state.v = v_term
        self.state.power = v_term * i
        self.state.power_setpoint = power_setpoint
        self.state.loss = heat
        self.state.heat = heat


def simulate(n_steps: int = 10, dt: float = 1.0) -> pd.DataFrame:
    """Discharge a capacitor through a converter, with thermal coupling.

    The capacitor starts charged to 2.5 V on a 500 F bank (≈ 1.56 kJ);
    a :class:`Converter` with a :class:`FixedEfficiency` loss model draws
    100 W AC for ``n_steps`` seconds; an :class:`AmbientThermalModel`
    registers the capacitor and updates its temperature from the ohmic
    heat generated by the ESR.

    ``n_steps`` and the discharge power are chosen so the capacitor does
    not drop to a voltage low enough to saturate (a real supercap bank
    would also enforce a minimum operating voltage, not modelled here).

    Returns:
        DataFrame with per-step ``V_cap``, ``i``, ``heat``, and ``T``.
    """
    capacitor = Capacitor(
        capacitance=500.0,  # F
        esr=0.005,  # Ω (5 mΩ ESR)
        initial_voltage=2.5,  # V
        mass=1.0,
        specific_heat=1000.0,
        thermal_resistance=5.0,  # K/W (loosely coupled to ambient)
    )
    converter = Converter(
        loss_model=FixedEfficiency(0.98),
        max_power=200.0,
        storage=capacitor,
    )
    ambient = AmbientThermalModel(T_ambient=25.0)
    ambient.add_component(capacitor)

    log: dict[str, list[float]] = {"V_cap": [], "i": [], "heat": [], "T": []}
    for _ in range(n_steps):
        converter.step(-100.0, dt)  # discharge at 100 W AC
        ambient.step(dt)
        s = capacitor.state
        log["V_cap"].append(s.V_cap)
        log["i"].append(s.i)
        log["heat"].append(s.heat)
        log["T"].append(s.T)

    return pd.DataFrame(log)


if __name__ == "__main__":
    df = simulate()
    print(df)
