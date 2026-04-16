# Getting Started

## Prerequisites

- Python 3.12 or higher
- pip or [uv](https://docs.astral.sh/uv/) (recommended)

## Installation

```bash
pip install simses
```

Or with uv:

```bash
uv add simses
```

## First Simulation

The example below runs a simple battery charge/discharge cycle and prints the
final state of charge.

```python
import numpy as np
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

# Create a 13s1p LFP battery string
battery = Battery(cell=SonyLFP(), serial=13, parallel=1)

dt = 60  # timestep in seconds

# Charge at 5 kW for 1 hour, then discharge
charge_profile = np.full(60, 5000.0)   # positive = charging
discharge_profile = np.full(60, -5000.0)

for power in np.concatenate([charge_profile, discharge_profile]):
    battery.step(power, dt)

print(f"SOC:     {battery.state.soc:.2%}")
print(f"Voltage: {battery.state.voltage:.1f} V")
```

!!! tip
    [PLACEHOLDER: Add a note about sign convention — positive = charging]

## What to Read Next

- [Battery Model Concepts](concepts/battery.md) — understand the ECM and circuit model
- [Choosing a Cell Model](guides/cell-models.md) — NMC vs LFP options
- [Demo Tutorial](tutorials/index.md) — interactive notebook with full examples
