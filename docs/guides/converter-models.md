# Choosing a Converter Model

simses ships six built-in AC/DC converter loss models. All implement the [`ConverterLossModel`][simses.converter.converter.ConverterLossModel] protocol and operate on normalised power (p.u. of the converter's rated `max_power`).

## Comparison

| Model | Loss shape | Data source | Direction symmetry | Constructor args |
|---|---|---|---|---|
| [`FixedEfficiency`](#fixedefficiency) | Constant η per direction | User-supplied | Symmetric by default; asymmetric via `(charge, discharge)` tuple | `eff: float \| tuple[float, float]` |
| [`Notton`](#notton) | Generic fit `η(p) = p / (p + P0 + K·p²)` | Notton et al. 2010 (three published inverter types) | Symmetric | `coefficients: (P0, K) = TYPE_2` |
| [`Bonfiglioli`](#bonfiglioli) | Notton form with per-direction coefficients and minimum-efficiency floor | F. Müller thesis — datasheet or FCR field data | Datasheet symmetric; field-data asymmetric | `coefficients: 6-tuple = DATASHEET` |
| [`Sungrow`](#sungrow) | Three selectable fit families, per-direction coefficients, discharge floor for notton/rampinelli | F. Müller thesis — FCR field data | Asymmetric | `fit: "notton" \| "rampinelli" \| "rational"` |
| [`SinamicsS120`](#sinamicss120) | 101-point lookup built from measured efficiency curves | Schimpe et al. 2018 | Symmetric by default; asymmetric via `use_discharging_curve=True` | `use_discharging_curve: bool = False` |
| [`SinamicsS120Fit`](#sinamicss120fit) | Closed-form fit `loss(p) = k₀(1 − e^(−m₀|p|)) + k₁|p| + k₂|p|²` | Least-squares fit to Schimpe 2018 data | Symmetric | (none) |

At runtime all loss models except `FixedEfficiency` evaluate to linear interpolation on a 201-point internal table (101 per direction, mirrored about zero) — the distinction is how those points were generated.

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

## `Notton`

A generic parametric PV-inverter loss family with efficiency `η(p) = p / (p + P0 + K·p²)`, where `p` is the magnitude of normalised power. Three published coefficient sets from the reference paper are provided as class attributes — `TYPE_1`, `TYPE_2` (default), `TYPE_3` — representing different inverter technologies. Use this when you have no manufacturer-specific data but want a physically reasonable two-parameter fit.

Source: Notton, G., Lazarov, V., Stoyanov, L. *Optimal sizing of a grid-connected PV system for various PV module technologies and inclinations, inverter efficiency characteristics and locations*, [Renewable Energy 35(2) (2010) 541–554](https://doi.org/10.1016/j.renene.2009.07.013).

```python
from simses.converter import Converter
from simses.model.converter.notton import Notton

converter = Converter(
    loss_model=Notton(),                         # Type 2 inverter by default
    max_power=100_000,
    storage=battery,
)

# Or with custom coefficients:
converter = Converter(
    loss_model=Notton(coefficients=(0.01, 0.04)),
    max_power=100_000,
    storage=battery,
)
```

## `Bonfiglioli`

Bonfiglioli RPS TL-4Q inverter. Uses the Notton form but with asymmetric charge/discharge coefficients and a minimum-efficiency floor that clips the curve at low normalised power — important for realistic idling behaviour in high-duty applications. Two published coefficient sets:

- `DATASHEET` (default): manufacturer datasheet measurements. Symmetric ch/dch (`P0=0.0072, K=0.034, min_eff=0.58`).
- `FIELD_DATA`: measured on FCR battery systems. Asymmetric, with lower minimum efficiencies — reflects real deployment losses including auxiliary consumption.

Source: F. Müller (M.Sc. thesis, TUM) — Notton fit of the [Bonfiglioli RPS TL-4Q datasheet](http://www.docsbonfiglioli.com/pdf_documents/catalogue/VE_CAT_RTL-4Q_STD_ENG-ITA_R00_5_WEB.pdf) with a complementary field-measured dataset.

```python
from simses.converter import Converter
from simses.model.converter.bonfiglioli import Bonfiglioli

converter = Converter(
    loss_model=Bonfiglioli(),                    # datasheet data
    max_power=100_000,
    storage=battery,
)

# Field-measured data (asymmetric, lower min η):
converter = Converter(
    loss_model=Bonfiglioli(Bonfiglioli.FIELD_DATA),
    max_power=100_000,
    storage=battery,
)
```

## `Sungrow`

Sungrow SC1000TL manufacturer-specific fit, also backed by field data from a frequency containment reserve (FCR) battery system. Three fit families are selectable via the `fit` argument:

- `"notton"` (default): classic Notton form. Discharge branch is clipped at a 0.21 minimum efficiency floor.
- `"rampinelli"`: three-parameter loss polynomial `p / (p + K0 + K1·p + K2·p²)`. Same discharge floor.
- `"rational"`: direct rational efficiency curve `(a1·p + a0) / (p² + b1·p + b0)`. No floor — the rational form stays bounded naturally.

All three use asymmetric charge/discharge coefficients. Use the rational fit when the Notton/Rampinelli floor clipping produces a visibly flat region you'd rather not see in your efficiency curve.

Source: F. Müller (M.Sc. thesis, TUM) — field fit on a Sungrow SC1000TL inverter.

```python
from simses.converter import Converter
from simses.model.converter.sungrow import Sungrow

converter = Converter(
    loss_model=Sungrow(),                        # notton fit by default
    max_power=1_000_000,                         # 1 MW rated
    storage=battery,
)

converter = Converter(
    loss_model=Sungrow(fit="rational"),
    max_power=1_000_000,
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
- [Models API reference](../api/models.md) — the six shipped loss models.
