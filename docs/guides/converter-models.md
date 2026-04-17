# Choosing a Converter Model

simses ships three built-in AC/DC converter loss models. All three implement the [`ConverterLossModel`][simses.converter.converter.ConverterLossModel] protocol and operate on normalised power (p.u. of the converter's rated `max_power`).

## Comparison

| Model | Loss shape | Data source | Direction symmetry | Constructor args |
|---|---|---|---|---|
| [`FixedEfficiency`](#fixedefficiency) | Constant η per direction | User-supplied | Symmetric by default; asymmetric via `(charge, discharge)` tuple | `eff: float \| tuple[float, float]` |
| [`SinamicsS120`](#sinamicss120) | 101-point lookup built from measured efficiency curves | Schimpe et al. 2018 | Symmetric by default; asymmetric via `use_discharging_curve=True` | `use_discharging_curve: bool = False` |
| [`SinamicsS120Fit`](#sinamicss120fit) | Closed-form fit `loss(p) = k₀(1 − e^(−m₀|p|)) + k₁|p| + k₂|p|²` | Least-squares fit to the same Schimpe 2018 data | Symmetric | (none) |

At runtime all three evaluate to linear interpolation on a 101-point internal table — the distinction is how those points were generated.

## `FixedEfficiency`

Constant round-trip efficiency. The simplest loss model and the right default when you don't yet have a converter-specific curve or when a single number is all your study needs. Pass a scalar for a symmetric model, or a `(charge, discharge)` tuple when the two directions differ.

```python
from simses.converter import Converter
from simses.model.converter.fix_efficiency import FixedEfficiency

converter = Converter(
    loss_model=FixedEfficiency(0.95),           # or (0.96, 0.94) for asymmetry
    max_power=100_000,                           # 100 kW rated
    storage=battery,
)
```

## `SinamicsS120`

Lookup-table model built from measured efficiency curves for the Siemens Sinamics S120, a common utility-scale drive. The bundled CSV carries 1001 sample points, re-sampled down to 101 at construction. The measurement splits into `Charging` and `Discharging` columns that differ by a mean of 0.23 % and a maximum of 0.40 %. By default the charging curve is mirrored onto the discharge branch so the model is symmetric about zero; set `use_discharging_curve=True` to preserve the measured asymmetry.

Source: Schimpe, M., Naumann, M., Truong, N., Hesse, H., Englberger, S., Jossen, A. *Energy efficiency evaluation of grid connection scenarios for stationary battery energy storage systems*, [Energy Procedia 155 (2018) 77–101](https://doi.org/10.1016/j.egypro.2018.11.065).

```python
from simses.converter import Converter
from simses.model.converter.sinamics import SinamicsS120

converter = Converter(
    loss_model=SinamicsS120(),                   # or use_discharging_curve=True
    max_power=100_000,
    storage=battery,
)
```

## `SinamicsS120Fit`

A closed-form parametric fit to the same Schimpe et al. 2018 dataset. The loss curve is a sum of three terms — a saturating exponential (captures the no-load offset), a linear term, and a quadratic — fitted by least squares. Use this when you want a smooth analytical shape (no lookup artefacts) or prefer to avoid the bundled CSV dependency. Symmetric about zero by construction.

Source: same as [`SinamicsS120`](#sinamicss120).

```python
from simses.converter import Converter
from simses.model.converter.sinamics import SinamicsS120Fit

converter = Converter(
    loss_model=SinamicsS120Fit(),
    max_power=100_000,
    storage=battery,
)
```

## Extending

Writing a new converter loss model means implementing `ac_to_dc(power_norm)` and `dc_to_ac(power_norm)` on normalised power. See [Extending Converter Loss Models](extending-converters.md) for the full walkthrough, including the reciprocity trap and the lookup-table pattern that avoids it.

## See Also

- [Converter concept](../concepts/converter.md) — how `ConverterLossModel` composes into `Converter`, the two-pass resolution, and sign handling at the AC/DC boundary.
- [`Converter` API reference](../api/converter.md).
- [Models API reference](../api/models.md) — the three shipped loss models.
