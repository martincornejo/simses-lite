# Extending Degradation Models

How to implement new calendar and cyclic aging laws, compose them into a `DegradationModel`, and plug them into the existing test suite.

!!! info "Who this is for"
    Researchers fitting an aging model to measurement data, or engineers wanting to simulate a chemistry whose aging differs from the Naumann LFP defaults. For the conceptual picture — SoH axes, running totals, why sub-models are stateless — see [Degradation concept](../concepts/degradation.md) first.

## The two protocols

Degradation splits into two independent sub-models, each a [`Protocol`][simses.degradation.calendar.CalendarDegradation]. Neither requires inheritance — structural subtyping only.

### `CalendarDegradation`

Fires **every timestep** — even when the battery is idle.

```python
def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float: ...
def update_resistance(self, state: BatteryState, dt: float, accumulated_rinc: float) -> float: ...
```

- `state` — current battery state (read SOC, T, etc.).
- `dt` — timestep in seconds.
- `accumulated_qloss` / `accumulated_rinc` — calendar capacity loss and resistance increase accumulated so far (p.u., ≥ 0). Your model reads these to continue a non-linear aging law under varying stress; memoryless laws (linear in time) can ignore them.
- Returns a **non-negative delta** — never an absolute value.

### `CyclicDegradation`

Fires **only on completed half-cycles** — `DegradationModel` delegates to the `HalfCycleDetector` for triggering.

```python
def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float: ...
def update_resistance(self, state: BatteryState, half_cycle: HalfCycle, accumulated_rinc: float) -> float: ...
```

- `half_cycle` — a [`HalfCycle`][simses.degradation.cycle_detector.HalfCycle] carrying `depth_of_discharge`, `mean_soc`, `c_rate`, and `full_equivalent_cycles`.
- Same accumulator pattern on both sides — virtual-FEC continuation available when the law is non-linear in throughput.
- Same delta-only return convention.

### The statelessness rule

Both sub-models must be **stateless**. All accumulators live on the [`DegradationState`][simses.degradation.state.DegradationState] that `DegradationModel` owns. The framework passes `accumulated_qloss` into `update_capacity` and `accumulated_rinc` into `update_resistance` so your model can reconstruct history without storing anything internally. Memoryless laws (linear-in-time calendar R rise, linear-in-FEC cyclic R rise) are free to ignore the accumulator.

This rule keeps checkpointing, warm-starts, and sub-model swapping trivial — the only state lives in one place.

## Worked walkthrough: √t calendar + DoD² cyclic

[`examples/extending/custom_degradation.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_degradation.py) implements a minimal pair:

**Calendar** — `q_cal(t) = s(T) · √t` with a temperature-dependent stress factor, using virtual-time continuation to stay correct under varying T:

```python
import math
from simses.battery.state import BatteryState


class SqrtTimeCalendar:
    K_REF = 1e-5          # [1/sqrt(s)] loss rate at T_ref
    T_REF = 25.0          # [°C]
    T_ACC = 20.0          # [K] Q10-style acceleration

    def _stress(self, T: float) -> float:
        return self.K_REF * math.exp((T - self.T_REF) / self.T_ACC)

    def update_capacity(self, state: BatteryState, dt: float, accumulated_qloss: float) -> float:
        stress = self._stress(state.T)
        if stress <= 0.0:
            return 0.0
        t_virt = (accumulated_qloss / stress) ** 2
        return stress * math.sqrt(t_virt + dt) - accumulated_qloss

    def update_resistance(self, state: BatteryState, dt: float, accumulated_rinc: float) -> float:
        return 1e-8 * self._stress(state.T) / self.K_REF * dt
```

The capacity method inverts the √t law at each call to find the *virtual* time that would have produced `accumulated_qloss` under the *current* stress, then steps forward — so T can change between steps without double-counting. If your law is linear in time (`dq = k · dt`), just ignore the accumulator and return `k(state) · dt`. If it follows a different exponent (`t^0.75`, SEI double-exponential, etc.), apply the same inversion principle with the right formula. The same principle applies to `update_resistance` via `accumulated_rinc` when the R-rise law is non-linear in time.

**Cyclic** — `Δq_cyc = K_CYC · DoD² · ΔFEC` per completed half-cycle, no memory across cycles:

```python
from simses.degradation.cycle_detector import HalfCycle


class DodSquaredCyclic:
    K_CYC = 1e-2
    K_RINC = 5e-3

    def update_capacity(self, state: BatteryState, half_cycle: HalfCycle, accumulated_qloss: float) -> float:
        return self.K_CYC * half_cycle.depth_of_discharge**2 * half_cycle.full_equivalent_cycles

    def update_resistance(self, state: BatteryState, half_cycle: HalfCycle, accumulated_rinc: float) -> float:
        return self.K_RINC * half_cycle.depth_of_discharge**2 * half_cycle.full_equivalent_cycles
```

## Composing and attaching

A `DegradationModel` combines the two sub-models with a `HalfCycleDetector` seeded by the battery's initial SOC:

```python
from simses.degradation import DegradationModel

degradation = DegradationModel(
    calendar=SqrtTimeCalendar(),
    cyclic=DodSquaredCyclic(),
    initial_soc=0.5,
)

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 10),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=degradation,
)
```

### Calendar-only / cyclic-only

For studies where you want only one mechanism active — decomposing an observed fade curve against experiment, isolating the effect of cycling, etc. — two factory methods inject a no-op on the other leg:

```python
DegradationModel.calendar_only(SqrtTimeCalendar(), initial_soc=0.5)
DegradationModel.cyclic_only(DodSquaredCyclic(), initial_soc=0.5)
```

### Warm-starting from a prior history

Pass an explicit `DegradationState` to start from a non-fresh battery:

```python
from simses.degradation.state import DegradationState

prior = DegradationState(qloss_cal=0.05, qloss_cyc=0.02)
DegradationModel(
    calendar=SqrtTimeCalendar(), cyclic=DodSquaredCyclic(),
    initial_soc=0.5, initial_state=prior,
)
```

The virtual-time / virtual-FEC continuation picks up seamlessly from the accumulated damage.

## Testing with the spec registries

`tests/test_degradation_models.py` keeps two separate registries — calendar and cyclic can be tested independently. Append a spec to each:

```python
# tests/test_degradation_models.py
CALENDAR_SPECS = [
    CalendarModelSpec(name="SonyLFPCalendar", factory=SonyLFPCalendarDegradation),
    CalendarModelSpec(name="SqrtTimeCalendar", factory=SqrtTimeCalendar),
]

CYCLIC_SPECS = [
    CyclicModelSpec(name="SonyLFPCyclic", factory=SonyLFPCyclicDegradation),
    CyclicModelSpec(name="DodSquaredCyclic", factory=DodSquaredCyclic),
]
```

The generic tests check:

- Positive capacity loss and resistance rise under realistic stress.
- Zero-`dt` / zero-FEC yields zero degradation.
- More time / more FEC produces more loss (monotonicity).

Model-specific tests (e.g. the `SonyLFP` √t-behaviour test and the accumulated-loss-continuity test) live alongside the generic ones in the same file — copy the `TestSonyLFPCalendar` class as a template for a targeted behaviour check on your own model.

## Shipping as a cell default

Once your calendar and cyclic pair is written, wire it into a `CellType` subclass so `Battery(..., degradation=True)` works out of the box:

```python
from simses.battery.cell import CellType
from simses.degradation import DegradationModel


class MyCell(CellType):
    # ... __init__, open_circuit_voltage, internal_resistance ...

    @classmethod
    def default_degradation_model(
        cls,
        initial_soc: float,
        initial_state=None,
    ) -> DegradationModel:
        return DegradationModel(
            calendar=SqrtTimeCalendar(),
            cyclic=DodSquaredCyclic(),
            initial_soc=initial_soc,
            initial_state=initial_state,
        )
```

See [Extending Cell Models](extending-cells.md#shipping-a-default-degradation-model) for the complete cell-class context.

## See Also

- [Degradation concept](../concepts/degradation.md) — SoH axes, running totals, virtual-time continuation.
- [`examples/extending/custom_degradation.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_degradation.py) — the full runnable walkthrough.
- [`SonyLFPCalendarDegradation`][simses.model.degradation.sony_lfp_calendar.SonyLFPCalendarDegradation] and [`SonyLFPCyclicDegradation`][simses.model.degradation.sony_lfp_cyclic.SonyLFPCyclicDegradation] — reference implementations grounded in the Naumann 2018 / 2020 measurements.
- [`CalendarDegradation`][simses.degradation.calendar.CalendarDegradation] / [`CyclicDegradation`][simses.degradation.cyclic.CyclicDegradation] API reference.
