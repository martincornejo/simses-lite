# Multi-String Systems

A multi-string BESS consists of multiple independent battery strings that share
a common power setpoint. simses supports this by operating multiple `Battery`
(or `Converter`) objects in parallel and distributing power between them.

## Basic Setup

[PLACEHOLDER: Show how to create two Battery strings]

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

string_a = Battery(cell=SonyLFP(), serial=13, parallel=1)
string_b = Battery(cell=SonyLFP(), serial=13, parallel=1)
strings = [string_a, string_b]
```

## Power Distribution Strategies

When multiple strings have different SOC values, power must be distributed
between them. Common strategies include:

### Equal Split

Divide the total power equally among all strings.

[PLACEHOLDER: Code snippet for equal power split]

### SOC-Weighted Split

Distribute power proportionally to each string's SOC (charge more when SOC is
low, discharge more when SOC is high).

[PLACEHOLDER: Code snippet for SOC-weighted distribution — reference demo notebook Part 3]

!!! note
    The demo notebook (Part 3 — Two Strings) demonstrates SOC-weighted power
    distribution in detail. See [Tutorials](../tutorials/index.md).

## Convergence Considerations

[PLACEHOLDER: Note on iterative power matching for strings with different SOC]

## See Also

- [Demo Tutorial](../tutorials/index.md) — Part 3 covers two-string operation
- [`Battery` API reference](../api/battery.md)
