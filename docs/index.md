# simses

**A Python simulator for battery energy storage systems (BESS).**

simses models battery systems using equivalent circuit models (ECM) with
series-parallel cell configurations and AC/DC converter loss models.
It supports thermal behavior and battery aging (degradation) simulation.

## Features

- Equivalent-circuit cell models (NMC, LFP) with lookup or analytical OCV/Rint
- Series-parallel battery string configuration
- AC/DC converter loss models (fixed efficiency, Sinamics S120)
- Thermal container models with HVAC and solar heat load
- Calendar and cyclic degradation models

## Installation

```bash
pip install simses
```

Python 3.12+ is required.

## Quick Start

```python
import numpy as np
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(cell=SonyLFP(), serial=13, parallel=1)

dt = 60  # seconds
for power in np.full(100, -5000):  # 5 kW discharge for 100 minutes
    battery.update(power, dt)

print(f"Final SOC: {battery.state.soc:.2%}")
```

## Navigation

- [Getting Started](getting-started.md) — install, first simulation, next steps
- [Tutorials](tutorials/index.md) — interactive demo notebook
- [API Reference](api/index.md) — full API documentation
