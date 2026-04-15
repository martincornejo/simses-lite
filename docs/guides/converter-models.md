# Choosing a Converter Model

Converter loss models determine how much power is lost in AC/DC conversion.
All models implement `ac_to_dc()` and `dc_to_ac()` with normalized power (p.u.
of `max_power`).

## Available Models

### Fixed Efficiency (`FixedEfficiency`)

A constant round-trip efficiency for charge and discharge.

```python
from simses.model.converter.fix_efficiency import FixedEfficiency
from simses.converter import Converter

loss_model = FixedEfficiency(efficiency=0.97)
converter = Converter(storage=battery, loss_model=loss_model, max_power=100_000)
```

### Sinamics S120 Lookup (`SinamicsS120`)

A lookup-table loss model based on measured Sinamics S120 efficiency data.

[PLACEHOLDER: Describe — CSV lookup, interpolated over normalized power]

```python
from simses.model.converter.sinamics import SinamicsS120

loss_model = SinamicsS120()
```

### Sinamics S120 Parametric (`SinamicsS120Fit`)

A parametric fit of the Sinamics S120 data — faster to evaluate than the
lookup table.

[PLACEHOLDER: Describe the parametric model]

## Comparison

| Model | Data source | Speed | Accuracy |
|---|---|---|---|
| `FixedEfficiency` | Constant | Fastest | Low |
| `SinamicsS120` | CSV lookup | Medium | High |
| `SinamicsS120Fit` | Parametric fit | Fast | Medium-high |

## Implementing a Custom Loss Model

[PLACEHOLDER: Describe the interface and provide a minimal example]

## See Also

- [Models API reference](../api/models.md)
- [Converter concept](../concepts/converter.md)
