# Choosing a Converter Model

simses ships ten built-in AC/DC converter loss models, split into two categories. **Fit families** (`Notton`, `AsymmetricNotton`, `Rampinelli`) are generic parametric forms that require explicit coefficients; the `NottonTypeN` subclasses are presets of published coefficients. **Product models** (`BonfiglioliTL4Q`, `BonfiglioliTL4QFieldData`, `SungrowSC1000TL`, `SinamicsS120`, `SinamicsS120Fit`) are specific manufacturer hardware with baked-in coefficients. All implement the [`ConverterLossModel`][simses.converter.converter.ConverterLossModel] protocol and operate on normalised power (p.u. of the converter's rated `max_power`).

## Comparison

### Fit families (parametric, require coefficients)

| Model | Loss shape | Constructor args |
|---|---|---|
| [`Notton`](#notton) | `η(p) = p / (p + P0 + K·p²)`, symmetric | `P0: float, K: float` |
| [`AsymmetricNotton`](#asymmetricnotton) | Notton form with independent charge and discharge coefficients | `charge: (P0, K), discharge: (P0, K)` |
| [`Rampinelli`](#rampinelli) | `η(p) = p / (p + K0 + K1·p + K2·p²)`, symmetric | `K0: float, K1: float, K2: float` |
| [`NottonType1`](#nottontypen), [`NottonType2`](#nottontypen), [`NottonType3`](#nottontypen) | Three published inverter presets from Notton et al. 2010 | (none — no-arg subclasses of `Notton`) |

### Product models (specific hardware, no-arg constructors)

| Model | Inherits from | Data source | Direction symmetry |
|---|---|---|---|
| [`FixedEfficiency`](#fixedefficiency) | — | User-supplied | Symmetric by default; asymmetric via `(charge, discharge)` tuple |
| [`BonfiglioliTL4Q`](#bonfigliolitl4q) | `Notton` | F. Müller thesis — RPS TL-4Q datasheet | Symmetric |
| [`BonfiglioliTL4QFieldData`](#bonfigliolitl4qfielddata) | `AsymmetricNotton` | F. Müller thesis — FCR field data | Asymmetric |
| [`SungrowSC1000TL`](#sungrowsc1000tl) | `AsymmetricNotton` | F. Müller thesis — FCR field data | Asymmetric |
| [`SinamicsS120`](#sinamicss120) | — | Schimpe et al. 2018 (measured) | Symmetric by default; asymmetric via `use_discharging_curve=True` |
| [`SinamicsS120Fit`](#sinamicss120fit) | — | Schimpe et al. 2018 (parametric fit) | Symmetric |

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

A generic parametric PV-inverter loss family with efficiency `η(p) = p / (p + P0 + K·p²)`, where `p` is the magnitude of normalised power. Symmetric about zero. Use this when you have a Notton-form fit to measured data, or when you want a physically reasonable two-parameter baseline.

For custom asymmetric ch/dch use [`AsymmetricNotton`](#asymmetricnotton). For the three published inverter presets see [`NottonTypeN`](#nottontypen) below.

Source: Notton, G., Lazarov, V., Stoyanov, L. *Optimal sizing of a grid-connected PV system for various PV module technologies and inclinations, inverter efficiency characteristics and locations*, [Renewable Energy 35(2) (2010) 541–554](https://doi.org/10.1016/j.renene.2009.07.013).

```python
from simses.converter import Converter
from simses.model.converter.notton import Notton

converter = Converter(
    loss_model=Notton(P0=0.0072, K=0.0345),
    max_power=100_000,
    storage=battery,
)
```

## `AsymmetricNotton`

Notton-form fit with independent charge and discharge parameter sets. Each direction takes its own `(P0, K)` pair — useful for fitting converters whose measured efficiency curves differ between charging and discharging.

```python
from simses.converter import Converter
from simses.model.converter.notton import AsymmetricNotton

converter = Converter(
    loss_model=AsymmetricNotton(
        charge=(0.0072, 0.0345),
        discharge=(0.005, 0.018),
    ),
    max_power=100_000,
    storage=battery,
)
```

## `NottonTypeN`

Three published inverter presets from Notton et al. 2010, provided as no-arg subclasses of `Notton` for convenience:

- `NottonType1` — `P0 = 0.0145, K = 0.0437`
- `NottonType2` — `P0 = 0.0072, K = 0.0345`
- `NottonType3` — `P0 = 0.0088, K = 0.1149`

```python
from simses.converter import Converter
from simses.model.converter.notton import NottonType2

converter = Converter(
    loss_model=NottonType2(),
    max_power=100_000,
    storage=battery,
)
```

## `Rampinelli`

A three-parameter generalisation of the Notton form: `η(p) = p / (p + K0 + K1·p + K2·p²)`. The extra linear term lets the fit capture a wider range of measured efficiency curves — useful when a two-parameter Notton fit leaves a visible residual at mid-power.

Source: Rampinelli, G. A., Krenzinger, A., Chenlo Romero, F. *Mathematical models for efficiency of inverters used in grid connected photovoltaic systems*, [Renewable and Sustainable Energy Reviews 34 (2014) 578–587](https://doi.org/10.1016/j.rser.2014.03.047).

```python
from simses.converter import Converter
from simses.model.converter.rampinelli import Rampinelli

converter = Converter(
    loss_model=Rampinelli(K0=0.003, K1=0.014, K2=0.003),
    max_power=100_000,
    storage=battery,
)
```

## `BonfiglioliTL4Q`

Bonfiglioli RPS TL-4Q inverter parameterised from the manufacturer datasheet — a `Notton` subclass with symmetric coefficients `P0 = 0.0072, K = 0.034`.

See [`BonfiglioliTL4QFieldData`](#bonfigliolitl4qfielddata) for the asymmetric variant parameterised from FCR field data.

Source: F. Müller (M.Sc. thesis, TUM) — Notton fit of the [Bonfiglioli RPS TL-4Q datasheet](http://www.docsbonfiglioli.com/pdf_documents/catalogue/VE_CAT_RTL-4Q_STD_ENG-ITA_R00_5_WEB.pdf).

```python
from simses.converter import Converter
from simses.model.converter.bonfiglioli import BonfiglioliTL4Q

converter = Converter(
    loss_model=BonfiglioliTL4Q(),
    max_power=100_000,
    storage=battery,
)
```

## `BonfiglioliTL4QFieldData`

Bonfiglioli RPS TL-4Q inverter parameterised from frequency containment reserve (FCR) battery-system field measurements — an `AsymmetricNotton` subclass with distinct charge and discharge coefficients. Reflects real deployment losses including auxiliary consumption that the datasheet curves do not capture. Charge: `P0 = 0.00195, K = 0.01349`. Discharge: `P0 = 0.00292, K = 0.03609`.

Source: F. Müller (M.Sc. thesis, TUM) — field fit on FCR BESS deployments of the Bonfiglioli RPS TL-4Q.

```python
from simses.converter import Converter
from simses.model.converter.bonfiglioli import BonfiglioliTL4QFieldData

converter = Converter(
    loss_model=BonfiglioliTL4QFieldData(),
    max_power=100_000,
    storage=battery,
)
```

## `SungrowSC1000TL`

Sungrow SC1000TL inverter, an `AsymmetricNotton` subclass backed by field data from an FCR battery system. Charge: `P0 = 0.007701864, K = 0.017290859`. Discharge: `P0 = 0.005511580, K = 0.018772838`.

The original thesis also characterised Rampinelli and rational-form fits of the same measurements; the Notton fit was the default in the legacy simses implementation and is the one ported here.

Source: F. Müller (M.Sc. thesis, TUM) — field fit on a Sungrow SC1000TL inverter.

```python
from simses.converter import Converter
from simses.model.converter.sungrow import SungrowSC1000TL

converter = Converter(
    loss_model=SungrowSC1000TL(),
    max_power=1_000_000,                         # 1 MW rated
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
- [Models API reference](../api/models.md) — all ten shipped loss models.
