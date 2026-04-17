"""Custom degradation models: √t calendar + DoD²-scaled cyclic.

Demonstrates minimal implementations of the
:class:`~simses.degradation.calendar.CalendarDegradation` and
:class:`~simses.degradation.cyclic.CyclicDegradation` protocols, then
composes them with :class:`~simses.degradation.degradation.DegradationModel`
and attaches the result to a :class:`Battery`.

Key protocol requirements exercised here:

* Both sub-models are stateless — all running totals live on
  :class:`~simses.degradation.state.DegradationState`, owned by
  :class:`DegradationModel`.
* The calendar model uses **virtual-time continuation** to remain correct
  under varying stress: given the accumulated loss, invert the √t law to
  find the virtual time that would have produced it under the current
  stress, then step forward from there.
* The cyclic model is triggered only on completed half-cycles and
  consumes the ``depth_of_discharge`` and ``full_equivalent_cycles``
  stress factors from the :class:`~simses.degradation.cycle_detector.HalfCycle`.

Coefficients are illustrative (not fitted to any real cell) — they are
scaled so that a short run shows visible SoH movement.
"""

import math

import pandas as pd

from simses.battery import Battery
from simses.battery.state import BatteryState
from simses.degradation import DegradationModel
from simses.degradation.cycle_detector import HalfCycle
from simses.model.cell.sony_lfp import SonyLFP


class SqrtTimeCalendar:
    """√t calendar aging with a temperature-dependent stress factor.

    Equation: ``q_cal(t) = s(T) · √t``, with
    ``s(T) = K_REF · exp((T − T_REF) / T_ACC)``.

    The ``update_capacity`` method inverts this law at every step to
    recover the *virtual* time consistent with the currently-accumulated
    loss under the current stress, then steps forward — so varying
    temperature between steps is handled transparently without any
    internal state.
    """

    K_REF = 1e-5  # [1/sqrt(s)] loss rate at T_ref
    T_REF = 298.15  # [K] reference temperature
    T_ACC = 20.0  # [K] Q10-style acceleration — +20 K doubles the rate

    def _stress(self, T: float) -> float:
        return self.K_REF * math.exp((T - self.T_REF) / self.T_ACC)

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        stress = self._stress(state.T)
        if stress <= 0.0:
            return 0.0
        t_virt = (accumulated_qloss / stress) ** 2
        return stress * math.sqrt(t_virt + dt) - accumulated_qloss

    def update_resistance(self, state: BatteryState, dt: float) -> float:
        """Resistance rise — linear in time, simple memoryless model."""
        return 1e-8 * self._stress(state.T) / self.K_REF * dt


class DodSquaredCyclic:
    """Cyclic aging: linear in FEC, scaled by DoD².

    Equation: ``Δq_cyc = K_CYC · DoD² · ΔFEC`` per completed half-cycle.

    Fired by :class:`DegradationModel` only on completed half-cycles, so
    the ``dt`` argument is replaced by a :class:`HalfCycle` carrying the
    stress factors. No memory across cycles is needed — each half-cycle
    contributes independently.
    """

    K_CYC = 1e-2  # [1/FEC at DoD=1] capacity loss
    K_RINC = 5e-3  # [1/FEC at DoD=1] resistance rise

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        return self.K_CYC * half_cycle.depth_of_discharge**2 * half_cycle.full_equivalent_cycles

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle) -> float:
        return self.K_RINC * half_cycle.depth_of_discharge**2 * half_cycle.full_equivalent_cycles


def simulate(n_cycles: int = 4, dt: float = 60.0) -> pd.DataFrame:
    """Run ``n_cycles`` charge/discharge half-hours and log degradation state.

    Args:
        n_cycles: Number of complete cycles (one cycle = 30 min charge +
            30 min discharge at 1 kW).
        dt: Seconds per step.

    Returns:
        DataFrame indexed by step with ``soh_Q``, ``soh_R``,
        ``qloss_cal``, and ``qloss_cyc`` columns.
    """
    degradation = DegradationModel(
        calendar=SqrtTimeCalendar(),
        cyclic=DodSquaredCyclic(),
        initial_soc=0.5,
    )
    battery = Battery(
        cell=SonyLFP(),
        circuit=(13, 10),  # 30 Ah, ~42 V
        initial_states={"start_soc": 0.5, "start_T": 308.15},  # 35 °C
        degradation=degradation,
    )

    steps_per_cycle = 60  # 30 min charge + 30 min discharge
    n_steps = n_cycles * steps_per_cycle

    log: dict[str, list[float]] = {"soh_Q": [], "soh_R": [], "qloss_cal": [], "qloss_cyc": []}
    for i in range(n_steps):
        half = i % steps_per_cycle < steps_per_cycle // 2
        battery.step(1000.0 if half else -1000.0, dt)
        log["soh_Q"].append(battery.state.soh_Q)
        log["soh_R"].append(battery.state.soh_R)
        log["qloss_cal"].append(degradation.state.qloss_cal)
        log["qloss_cyc"].append(degradation.state.qloss_cyc)

    return pd.DataFrame(log)


if __name__ == "__main__":
    df = simulate()
    print(df.iloc[::30])  # sample every 30 minutes
