# Extending Storage (Non-Battery)

How to plug a storage that is *not* a `Battery` — a supercapacitor bank, flow battery, hydrogen tank, or any custom energy buffer — into the existing `Converter` and thermal subsystems.

!!! info "Who this is for"
    Researchers simulating hybrid systems or exotic storage technologies. Advanced: the payoff is that `Converter`, `AmbientThermalModel`, and `ContainerThermalModel` are all duck-typed against narrow structural contracts — so a new storage doesn't need to subclass `Battery` or live inside the `simses.battery` package.

## The two contracts

Two small protocols govern what a storage must expose.

### Storage contract (for `Converter`)

`Converter` wraps anything with two members:

| Member | Type | Purpose |
|---|---|---|
| `step(power_setpoint, dt)` | method | Advance one timestep. ``power_setpoint`` is in W, sign-convention: positive = charging. |
| `state.power` | float | The actual delivered power this step (may differ from the setpoint if the storage saturated a limit). |

That's it. `Converter` reads `state.power` after calling `step()` to decide whether its [two-pass resolution](../concepts/converter.md#the-two-pass-resolution) needs to re-convert the AC side. No other attribute is required.

### `ThermalComponent` contract (for the thermal models)

To register a storage as a thermal node with [`AmbientThermalModel`][simses.thermal.ambient.AmbientThermalModel] or [`ContainerThermalModel`][simses.thermal.container.ContainerThermalModel], it must satisfy [`ThermalComponent`][simses.thermal.protocol.ThermalComponent] — four additional members:

| Member | Direction | Meaning |
|---|---|---|
| `state.T` | read / written | Component temperature in °C. |
| `state.heat` | read | Internal heat generation in W (+ = heats the component). |
| `thermal_capacity` | read | Lumped thermal capacity in J/K. |
| `thermal_resistance` | read | Thermal resistance to the surrounding air / ambient in K/W. |

The thermal model reads `heat` + the capacities / resistances, integrates one Euler step, and writes back the new `T` onto your storage's state. If you don't care about temperature, omit these four and skip the thermal models — the storage still works with `Converter`.

## What you do *not* get

Two battery-specific subsystems have no equivalent for arbitrary storage:

- **Degradation.** [`DegradationModel`][simses.degradation.degradation.DegradationModel] assumes `state.soh_Q` and `state.soh_R` and is wired in by `Battery.step()`. If your storage ages, build its own aging tracker; the `CalendarDegradation` / `CyclicDegradation` protocols and the `HalfCycleDetector` are not chemistry-neutral enough to reuse as-is.
- **Derating.** [`CurrentDerating`][simses.battery.derating.CurrentDerating] reads battery-specific state (SOC, C-rate limits, voltage window). If you need load-dependent current curtailment, build it into your `step()` method directly.

These are deliberate boundaries — keeping the battery-specific machinery in `simses.battery` stops it from leaking into unrelated storage kinds.

## Worked walkthrough: a lumped capacitor

[`examples/extending/capacitor_storage.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/capacitor_storage.py) implements a minimal supercapacitor with ESR. Three pieces — a state dataclass, a class with `step()`, and a `simulate()` that exercises both contracts.

State dataclass:

```python
from dataclasses import dataclass


@dataclass
class CapacitorState:
    Q: float            # stored charge [C]
    V_cap: float        # ideal-capacitor voltage [V]
    v: float = 0.0      # terminal voltage [V]
    i: float = 0.0      # current [A]
    power: float = 0.0  # delivered power [W]  ← required by Converter
    power_setpoint: float = 0.0
    loss: float = 0.0
    heat: float = 0.0   # ← required by ThermalComponent
    T: float = 25.0     # ← required by ThermalComponent
```

Storage class:

```python
import math


class Capacitor:
    def __init__(self, capacitance, esr, initial_voltage, *,
                 mass=1.0, specific_heat=1000.0, thermal_resistance=1.0,
                 initial_T=25.0):
        self.capacitance = capacitance
        self.esr = esr
        self.mass = mass
        self.specific_heat = specific_heat
        self.thermal_resistance = thermal_resistance   # ← ThermalComponent
        self.state = CapacitorState(
            Q=capacitance * initial_voltage,
            V_cap=initial_voltage,
            T=initial_T,
        )

    @property
    def thermal_capacity(self) -> float:               # ← ThermalComponent
        return self.mass * self.specific_heat

    def step(self, power_setpoint: float, dt: float) -> None:
        # Solve P = (V_cap + R_s · i) · i for i — same quadratic form as
        # the ECM in Battery, with V_cap playing the role of OCV.
        V_cap, R_s = self.state.V_cap, self.esr
        if power_setpoint == 0.0:
            i = 0.0
        else:
            discriminant = V_cap**2 + 4.0 * R_s * power_setpoint
            i = (-V_cap + math.sqrt(max(0.0, discriminant))) / (2.0 * R_s)

        self.state.Q += i * dt
        self.state.V_cap = self.state.Q / self.capacitance

        v_term = V_cap + R_s * i
        heat = R_s * i**2
        self.state.i = i
        self.state.v = v_term
        self.state.power = v_term * i                  # ← Converter reads this
        self.state.power_setpoint = power_setpoint
        self.state.loss = heat
        self.state.heat = heat                         # ← ThermalComponent reads this
```

The `step()` solves the same quadratic the battery ECM solves (`P = V·I` combined with `V = V_cap + R_s·I`), producing the physically meaningful current. Everything else is bookkeeping into state.

## Plugging into `Converter`

Because `Converter` only needs `step()` + `state.power`, a `Capacitor` drops in where a `Battery` would:

```python
from simses.converter import Converter
from simses.model.converter.fix_efficiency import FixedEfficiency

capacitor = Capacitor(capacitance=500.0, esr=0.005, initial_voltage=2.5)
converter = Converter(
    loss_model=FixedEfficiency(0.98),
    max_power=200.0,
    storage=capacitor,
)

converter.step(-100.0, dt=1.0)   # discharge at 100 W AC
```

When your storage can't deliver the commanded DC, `Converter`'s [two-pass resolution](../concepts/converter.md#the-two-pass-resolution) handles the recovery — but only if `state.power` reports the actually-delivered power, not the setpoint. A production storage should always implement this safeguard: any storage can saturate under some setpoint (voltage limits, SOC limits, thermal limits), and the two-pass resolution only works if you detect the saturation and write the truth to `state.power`. The shipped `Capacitor` example omits this for brevity — its `simulate()` stays within feasible bounds so the path is never triggered — but your own storage should not.

## Plugging into a thermal model

If you implemented the four `ThermalComponent` members, register the storage like any battery node:

```python
from simses.thermal import AmbientThermalModel

ambient = AmbientThermalModel(T_ambient=25.0)
ambient.add_component(capacitor)

for _ in range(n_steps):
    converter.step(-100.0, dt)
    ambient.step(dt)              # reads heat, writes T back on capacitor
```

Step ordering matters: call the thermal model's `step()` **after** all electrical components for the timestep have written their `state.heat`. See [Multi-String Systems](multi-string.md#shared-thermal-environment) for the same pattern with multiple batteries sharing one environment.

## Testing your storage

Unlike cells, converters, and degradation, there's no parameterised spec registry for storages (the library ships no non-battery storage). Write targeted tests in your own test module, exercising the contract directly:

```python
def test_capacitor_delivers_requested_power_under_limits():
    cap = Capacitor(capacitance=500.0, esr=0.005, initial_voltage=2.5)
    cap.step(-50.0, dt=1.0)
    assert cap.state.power == pytest.approx(-50.0, rel=0.05)


def test_capacitor_satisfies_thermal_component_contract():
    cap = Capacitor(capacitance=500.0, esr=0.005, initial_voltage=2.5)
    # structural checks — a regression safety net.
    assert isinstance(cap.state.T, float)
    assert isinstance(cap.state.heat, float)
    assert cap.thermal_capacity > 0
    assert cap.thermal_resistance > 0
```

The integration test for the shipped example is in `tests/test_examples.py::test_capacitor_storage` — it runs the full simulate-converter-plus-thermal pipeline and checks that heat raises the temperature and that `V_cap` monotonically decreases through a discharge. Mirror it for your storage.

## See Also

- [Converter concept](../concepts/converter.md) — the storage duck-typing contract and two-pass resolution.
- [Thermal Models concept](../concepts/thermal.md#the-thermalcomponent-contract) — what registering as a thermal node commits you to.
- [`examples/extending/capacitor_storage.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/capacitor_storage.py) — the full runnable walkthrough.
- [`ThermalComponent` API reference](../api/thermal.md).
