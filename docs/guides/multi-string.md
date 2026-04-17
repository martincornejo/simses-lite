# Multi-String Systems

Larger BESS installations — grid-scale, utility, or industrial — are typically built from several independent strings, each with its own converter, for modularity, redundancy, and staged deployment. simses has no dedicated multi-string class; instead, you compose N independent `(Battery, Converter)` pairs and apply a **power-distribution rule** on every timestep.

## Basic setup

Two strings, one `Battery` + one `Converter` each. The batteries can differ in chemistry, circuit, initial SOC, or C-rate; the converters can differ in loss model or rating.

```python
from simses.battery import Battery
from simses.converter import Converter
from simses.model.cell.sony_lfp import SonyLFP
from simses.model.converter.sinamics import SinamicsS120Fit


def make_string(start_soc, circuit=(104, 10), max_power=20_000):
    battery = Battery(
        cell=SonyLFP(),
        circuit=circuit,
        initial_states={"start_soc": start_soc, "start_T": 298.15},
    )
    converter = Converter(
        loss_model=SinamicsS120Fit(),
        max_power=max_power,
        storage=battery,
    )
    return battery, converter


strings = [
    make_string(start_soc=0.3, circuit=(104, 10), max_power=20_000),  # full-size
    make_string(start_soc=0.7, circuit=(104, 5),  max_power=10_000),  # half size, half power
]
```

## Equal split

The simplest rule: divide the total setpoint by `len(strings)`. Appropriate when all strings have identical ratings and SOCs track closely.

```python
def equal_split(strings, total_power):
    power_per_string = total_power / len(strings)
    for _, converter in strings:
        converter.step(power_per_string, dt)
```

This ignores SOC differences — over many cycles, strings drift apart, and the first to hit `soc_limits` silently stops contributing while the others keep running. Use this only as a baseline.

## SOC-weighted split

A better rule for strings that start at different SOCs or drift apart over time: on discharge, drain higher-SOC strings faster; on charge, fill lower-SOC strings faster. This is what the [demo notebook, Part 3](../tutorials/demo.ipynb) uses.

```python
import numpy as np


def soc_weighted_split(strings, total_power, eps=1e-6):
    socs = np.array([battery.state.soc for battery, _ in strings])
    if total_power < 0:                              # discharging
        weights = (socs + eps) / (socs + eps).sum()
    else:                                             # charging (or idle)
        weights = (1 - socs + eps) / (1 - socs + eps).sum()
    return total_power * weights


def step_strings(strings, total_power, dt):
    powers = soc_weighted_split(strings, total_power)
    for (_, converter), p in zip(strings, powers, strict=True):
        converter.step(p, dt)
```

The `eps` guards against the degenerate case where all strings are at the same boundary (all SOC = 0 on discharge, or all SOC = 1 on charge).

### Designing your own rule

The two rules above are starting points. A distribution rule is just a function from `(strings, total_power)` to per-string powers, so anything can go there — weightings that minimise cumulative aging, MPC over a receding horizon, thermal-aware splits that offload from hot strings, or a centralised optimiser that treats the multi-string system as a single decision variable. simses only requires that each converter's `step(power, dt)` is called per timestep with whatever value your strategy produced.

### Saturation caveat

Both rules above are **single-pass**: they compute a distribution from the pre-step state and apply it verbatim. If one string then saturates (`conv.state.power < commanded` because the battery hit a voltage, SOC, or thermal limit), the total AC power delivered to the system bus will be less than the commanded `total_power` — there is no automatic re-distribution to the non-saturated strings.

For studies where exact total power matters, either:

- Check `sum(conv.state.power for _, conv in strings)` after stepping and iterate — redistribute the unmet portion among strings that still have headroom.
- Upstream the distribution into an EMS (energy-management system) that tracks and compensates for saturation across steps.

## Shared thermal environment

Multiple strings in the same container share one thermal model — register each battery as a separate node via `add_component()`:

```python
from simses.thermal import AmbientThermalModel

thermal = AmbientThermalModel(T_ambient=298.15)
for battery, _ in strings:
    thermal.add_component(battery)
```

In the simulation loop, step the thermal model **after** all the electrical steps have written their `state.heat`:

```python
for i, load in enumerate(load_profile):
    step_strings(strings, total_power=-load, dt=dt)
    thermal.step(dt)
```

For richer setups (walls, HVAC, solar gain) swap `AmbientThermalModel` for [`ContainerThermalModel`](../concepts/thermal.md) — the `add_component()` contract is the same.

## Encapsulating the whole system as a single class

The patterns above — a list of `(Battery, Converter)` tuples, an external distribution function, an external thermal model — are the simplest way to express a multi-string system. For larger projects, you can wrap all of it (strings, split rule, thermal environment) behind a single class that exposes `step(power, dt)` and a `state.power` attribute. Because `Converter` duck-types its storage (see the [Converter concept page](../concepts/converter.md)), such a wrapper fits anywhere a `Battery` does — an upstream `Converter` can chain onto it, a higher-level EMS or co-simulation bridge sees one interface, and the internal multi-string composition stays fully encapsulated.

## See Also

- [Demo tutorial, Part 3](../tutorials/demo.ipynb) — full worked example with peak-shaving EMS on two strings of different sizes.
- [Demo tutorial, Part 4](../tutorials/demo.ipynb) — same two-string pack coupled to an `AmbientThermalModel`.
- [Battery concept](../concepts/battery.md) and [Converter concept](../concepts/converter.md) — what each string component owns and what saturates when limits bite.
- [Thermal Models concept](../concepts/thermal.md) — the `ThermalComponent` protocol and `add_component()` details.
