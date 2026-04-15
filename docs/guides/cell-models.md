# Choosing a Cell Model

simses provides two built-in cell models. Both implement the `CellType` interface
and can be used interchangeably in `Battery`.

## Available Models

### Samsung 94 Ah NMC (`Samsung94AhNMC`)

[PLACEHOLDER: Describe — NMC prismatic cell, analytical OCV curve, constant Rint]

```python
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC

cell = Samsung94AhNMC()
battery = Battery(cell=cell, serial=13, parallel=3)
```

### Sony LFP (`SonyLFP`)

[PLACEHOLDER: Describe — LFP cylindrical cell, analytical OCV, 2D interpolated Rint (SOC × Temperature)]

```python
from simses.model.cell.sony_lfp import SonyLFP

cell = SonyLFP()
battery = Battery(cell=cell, serial=13, parallel=1)
```

## Comparison

| Property | Samsung94AhNMC | SonyLFP |
|---|---|---|
| Chemistry | NMC | LFP |
| Format | Prismatic | Cylindrical |
| Rint model | Constant | 2D interpolated |
| OCV model | Analytical | Analytical |
| Nominal capacity | [PLACEHOLDER] | [PLACEHOLDER] |

## Implementing a Custom Cell Model

Subclass `CellType` and implement two methods:

```python
from simses.battery.cell import CellType

class MyCellModel(CellType):
    def open_circuit_voltage(self, state):
        ...

    def internal_resistance(self, state):
        ...
```

[PLACEHOLDER: Link to full CellType API reference]

## See Also

- [`CellType` API reference](../api/battery.md)
- [Models API reference](../api/models.md)
