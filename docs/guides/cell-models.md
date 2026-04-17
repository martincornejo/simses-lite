# Choosing a Cell Model

simses ships two built-in cell models. Both implement [`CellType`][simses.battery.cell.CellType] and slot interchangeably into `Battery`. The table below is the quick chooser; each cell is then documented in its own section with source and a runnable snippet.

## Comparison

| Model | Chemistry | Format | Nominal capacity | Nominal voltage | Voltage window | Max C-rate (ch / dis) | Rint model | Default aging |
|---|---|---|---|---|---|---|---|---|
| [`SonyLFP`](#sonylfp) | LFP | Cylindrical 26650 (26 × 65 mm) | 3.0 Ah | 3.2 V | 2.0 – 3.6 V | 1.0 / 6.6 | 2-D lookup in (SOC, T), separate charge/discharge curves | Yes (Naumann) |
| [`Samsung94AhNMC`](#samsung94ahnmc) | NMC | Prismatic (125 × 45 × 173 mm) | 94.0 Ah | 3.68 V | 2.7 – 4.15 V | 2.0 / 2.0 | Constant 0.819 mΩ | No |

All values are per cell, taken directly from the model constructors.

## `SonyLFP`

A small-format cylindrical LFP cell (Sony/Murata US26650FTC1) with a flat OCV plateau, strong cycle life, and a notably asymmetric C-rate (1.0 charge, 6.6 discharge). OCV, hysteresis, and the entropic coefficient are 1-D lookups in SOC; internal resistance is a 2-D lookup over (SOC, T) with separate charge and discharge tables. This is the only cell in the library that ships a default degradation pair — [Naumann 2018 calendar](https://doi.org/10.1016/j.est.2018.01.019) and [Naumann 2020 cyclic](https://doi.org/10.1016/j.jpowsour.2019.227666) — so multi-year stationary-storage runs with aging work out of the box.

Additional source: Naumann, M. *Techno-economic evaluation of stationary lithium-ion energy storage systems with special consideration of aging*. PhD Thesis, Technical University Munich, 2018.

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 1),
    initial_states={"start_soc": 0.5, "start_T": 298.15},
    degradation=True,                     # picks up the default Naumann pair
)
```

The `degradation=True` shortcut only works with cells that declare a `default_degradation_model()` — `SonyLFP` does. For warm-starting from a prior aging state, see [Degradation](../concepts/degradation.md).

## `Samsung94AhNMC`

A large-format prismatic NMC cell typical of modern stationary-storage installations. 94 Ah is in the range used by grid-scale container systems where large-format prismatic cells dominate today. OCV is analytical — a sum of four sigmoid terms plus a linear term, steeper than LFP in the working range and useful for SOC estimation. Internal resistance is constant (0.819 mΩ); hysteresis and entropic coefficient are zero. No default degradation model ships with this cell — attach one explicitly, or run without aging.

Source: Collath, N., Tepe, B., Englberger, S., Jossen, A., Hesse, H. *Suitability of late-life lithium-ion cells for battery energy storage systems*, [Journal of Energy Storage 87 (2024) 111508](https://doi.org/10.1016/j.est.2024.111508).

```python
from simses.battery import Battery
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC

battery = Battery(
    cell=Samsung94AhNMC(),
    circuit=(96, 1),
    initial_states={"start_soc": 0.5, "start_T": 298.15},
)
```

A 96-series string of these cells gives ≈ 353 V nominal with 94 Ah capacity — about 33 kWh of usable energy per string.

## Extending

Writing a new cell model means subclassing `CellType` and implementing `open_circuit_voltage()` and `internal_resistance()`, plus (optionally) `hysteresis_voltage()`, `entropic_coefficient()`, and `default_degradation_model()`. A dedicated extension guide is in progress; until it lands, the [Battery concept page](../concepts/battery.md) and the source of the two shipped models are the best reference.

## See Also

- [Battery concept](../concepts/battery.md) — how `CellType` composes into `Battery` and scales to pack level.
- [`CellType` API reference](../api/battery.md#cell-interface).
- [Models API reference](../api/models.md) — the `SonyLFP` and `Samsung94AhNMC` classes.
