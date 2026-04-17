# API Reference

Complete reference for all public classes and functions in simses.

## Modules

| Module | Description |
|---|---|
| [`simses.battery`](battery.md) | Battery system, state, cell interface, derating |
| [`simses.converter`](converter.md) | AC/DC converter wrapper |
| [`simses.degradation`](degradation.md) | Degradation models and state |
| [`simses.thermal`](thermal.md) | Thermal container and ambient models |
| [`simses.interpolation`](interpolation.md) | Fast scalar 1-D / 2-D linear interpolation helpers |
| [`simses.model.*`](models.md) | Concrete cell, converter, degradation, and thermal implementations |

## Quick Reference

### Battery

```python
from simses.battery import Battery, BatteryState
from simses.battery import CurrentDerating, DeratingChain
from simses.battery import LinearVoltageDerating, LinearThermalDerating
```

### Converter

```python
from simses.converter import Converter
```

### Degradation

```python
from simses.degradation import DegradationModel, DegradationState
from simses.degradation import CalendarDegradation, CyclicDegradation
from simses.degradation import HalfCycleDetector, HalfCycle
```

### Thermal

```python
from simses.thermal import AmbientThermalModel, ContainerThermalModel
from simses.thermal import ContainerProperties, ContainerLayer
from simses.thermal import HvacModel, ConstantCopHvac
from simses.thermal import ThermostatStrategy, ThermostatMode
from simses.thermal import SolarConfig, solar_heat_load
```

### Cell Models

```python
from simses.model.cell.sony_lfp import SonyLFP
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC
```

### Converter Loss Models

```python
from simses.model.converter.fix_efficiency import FixedEfficiency
from simses.model.converter.sinamics import SinamicsS120, SinamicsS120Fit
```
