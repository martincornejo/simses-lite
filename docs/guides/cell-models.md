# Choosing a Cell Model

simses ships four built-in cell models. All implement [`CellType`][simses.battery.cell.CellType] and slot interchangeably into `Battery`. The table below is the quick chooser; each cell is then documented in its own section with source and a runnable snippet.

## Comparison

| Model | Chemistry | Format | Nominal capacity | Nominal voltage | Voltage window | Max C-rate (ch / dis) | Rint model | Default aging |
|---|---|---|---|---|---|---|---|---|
| [`SonyLFP`](#sonylfp) | LFP | Cylindrical 26650 (26 × 65 mm) | 3.0 Ah | 3.2 V | 2.0 – 3.6 V | 1.0 / 6.6 | 2-D lookup in (SOC, T), separate charge/discharge curves | Yes (Naumann) |
| [`MolicelNMC`](#molicelnmc) | NMC | Cylindrical 18650 (18 × 65 mm) | 1.9 Ah | 3.7 V | 3.0 – 4.25 V | 1.05 / 2.1 | 1-D lookup in SOC (symmetric, T-independent) | Yes (Molicel) |
| [`PanasonicNCA`](#panasonicnca) | NCA | Cylindrical 18650 (18 × 65 mm) | 2.73 Ah | 3.6 V | 2.5 – 4.2 V | 0.5 / 3.5 | 1-D lookup in SOC, separate charge/discharge curves | No |
| [`Samsung94AhNMC`](#samsung94ahnmc) | NMC | Prismatic (125 × 45 × 173 mm) | 94.0 Ah | 3.68 V | 2.7 – 4.15 V | 2.0 / 2.0 | Constant 0.819 mΩ | No |

All values are per cell, taken directly from the model constructors.

## `SonyLFP`

A small-format cylindrical LFP cell (Sony/Murata US26650FTC1) with a flat OCV plateau, strong cycle life, and a notably asymmetric C-rate (1.0 charge, 6.6 discharge). OCV, hysteresis, and the entropic coefficient are 1-D lookups in SOC; internal resistance is a 2-D lookup over (SOC, T) with separate charge and discharge tables. Ships a default degradation pair — [Naumann 2018 calendar](https://doi.org/10.1016/j.est.2018.01.019) and [Naumann 2020 cyclic](https://doi.org/10.1016/j.jpowsour.2019.227666) — so multi-year stationary-storage runs with aging work out of the box.

Additional source: Naumann, M. *Techno-economic evaluation of stationary lithium-ion energy storage systems with special consideration of aging*. PhD Thesis, Technical University Munich, 2018.

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 1),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=True,                     # picks up the default Naumann pair
)
```

The `degradation=True` shortcut only works with cells that declare a `default_degradation_model()` — `SonyLFP` does. For warm-starting from a prior aging state, see [Degradation](../concepts/degradation.md).

## `MolicelNMC`

An 18650 cylindrical NMC cell (Molicel INR-18650-NMC) with moderate power capability (1.05 C charge, 2.1 C discharge). OCV is analytical — a sum of four sigmoid terms plus a linear term. Internal resistance is a 1-D lookup in SOC; the source characterisation is symmetric for charge and discharge and temperature-independent in the tested range. Ships a default degradation pair adapted to the Naumann structure: `t^0.75` calendar capacity fade with `√t` resistance rise, and a `Q^0.5562` power-law cyclic law in charge throughput. Both legs track capacity fade *and* resistance rise, making it a good reference cell for NMC aging studies.

Source: Schuster, S. F., Bach, T., Fleder, E., Müller, J., Brand, M., Sextl, G., Jossen, A. *Nonlinear aging characteristics of lithium-ion cells under different operational conditions*, [Journal of Energy Storage 1 (2015) 44–53](https://doi.org/10.1016/j.est.2015.05.003).

```python
from simses.battery import Battery
from simses.model.cell.molicel_nmc import MolicelNMC

battery = Battery(
    cell=MolicelNMC(),
    circuit=(14, 4),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=True,                     # picks up the default Molicel pair
)
```

A 14-series × 4-parallel arrangement gives ≈ 52 V nominal with 7.6 Ah, about 380 Wh — suited to small mobile applications. The cyclic law omits the asymmetric C-rate branching of the legacy reference: it requires charge/discharge direction on the `HalfCycle`, which the detector does not expose. DoD is the dominant stress factor and is preserved.

## `PanasonicNCA`

A conservative-charge 18650 NCA cell (Panasonic NCR18650) with a 0.5 C charge / 3.5 C discharge envelope — the low charge rate reflects the published limit for long calendar life. OCV is analytical (sum of four sigmoids plus a linear term); internal resistance is a 1-D lookup in SOC with separate charge and discharge curves (charge and discharge differ at every SOC in the source data). No default degradation model ships — the legacy reference has a solid calendar model (Arrhenius with voltage-cubic stress) but no matching cyclic pair, so combining them would be misleading. Attach a model explicitly, or run without aging.

Source: Keil, P., Schuster, S. F., Wilhelm, J., Travi, J., Hauser, A., Karl, R. C., Jossen, A. *Calendar aging of lithium-ion batteries*, [Journal of The Electrochemical Society 163(9) (2016) A1872–A1880](https://doi.org/10.1149/2.0411609jes).

```python
from simses.battery import Battery
from simses.model.cell.panasonic_nca import PanasonicNCA

battery = Battery(
    cell=PanasonicNCA(),
    circuit=(14, 4),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
)
```

A 14-series × 4-parallel arrangement gives ≈ 50 V nominal with 10.9 Ah, about 550 Wh.

## `Samsung94AhNMC`

A large-format prismatic NMC cell typical of modern stationary-storage installations. 94 Ah is in the range used by grid-scale container systems where large-format prismatic cells dominate today. OCV is analytical — a sum of four sigmoid terms plus a linear term, steeper than LFP in the working range and useful for SOC estimation. Internal resistance is constant (0.819 mΩ); hysteresis and entropic coefficient are zero. No default degradation model ships with this cell — attach one explicitly, or run without aging.

Source: Collath, N., Tepe, B., Englberger, S., Jossen, A., Hesse, H. *Suitability of late-life lithium-ion cells for battery energy storage systems*, [Journal of Energy Storage 87 (2024) 111508](https://doi.org/10.1016/j.est.2024.111508).

```python
from simses.battery import Battery
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC

battery = Battery(
    cell=Samsung94AhNMC(),
    circuit=(96, 1),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
)
```

A 96-series string of these cells gives ≈ 353 V nominal with 94 Ah capacity — about 33 kWh of usable energy per string.

## Extending

Writing a new cell model means subclassing `CellType` and implementing `open_circuit_voltage()` and `internal_resistance()`, plus (optionally) `hysteresis_voltage()`, `entropic_coefficient()`, and `default_degradation_model()`. See [Extending Cell Models](extending-cells.md) for the full walkthrough, including the test-harness hookup and the CSV-backed lookup pattern.

## See Also

- [Battery concept](../concepts/battery.md) — how `CellType` composes into `Battery` and scales to pack level.
- [`CellType` API reference](../api/battery.md#cell-interface).
- [Models API reference](../api/models.md) — the four shipped cell classes.
