# Battery API

The `simses.battery` module holds the top-level [`Battery`][simses.battery.battery.Battery] simulator, its mutable state, the [`CellType`][simses.battery.cell.CellType] ABC that chemistry implementations subclass, the per-cell property dataclasses, cell-format presets, and current-derating strategies. For the system-level framing — ECM, series-parallel scaling, `step()` lifecycle — see the [Battery concept page](../concepts/battery.md).

## Battery system

Top-level simulator. Composes a `CellType` with a `(serial, parallel)` circuit, solves the ECM for the equilibrium current at each step, clamps to hard limits, and optionally applies derating and degradation.

::: simses.battery.battery.Battery

## State

Plain mutable dataclass mutated in place by `Battery.step()`. No methods — all logic is in `Battery`.

::: simses.battery.state.BatteryState

## Cell interface

Abstract base class for cell chemistries — the "datasheet" side of the composition. Required methods: `open_circuit_voltage`, `internal_resistance`. Optional overrides for hysteresis, entropic coefficient, and a default degradation model. See [Extending Cell Models](../guides/extending-cells.md).

::: simses.battery.cell.CellType

## Cell properties

Per-cell electrical and thermal parameter dataclasses passed to `CellType.__init__`. Every chemistry supplies one of each.

::: simses.battery.properties.ElectricalCellProperties

::: simses.battery.properties.ThermalCellProperties

## Cell formats

Physical format descriptors used to compute surface area and volume for thermal coupling. The two 26650 / 18650 presets bundle common dimensions.

::: simses.battery.format.CellFormat

::: simses.battery.format.PrismaticCell

::: simses.battery.format.RoundCell

::: simses.battery.format.RoundCell18650

::: simses.battery.format.RoundCell26650

## Derating

Optional current-curtailment strategies applied *after* hard limits. Protocol-based — use the shipped linear voltage / thermal strategies, compose them with `DeratingChain`, or implement your own.

::: simses.battery.derating.CurrentDerating

::: simses.battery.derating.DeratingChain

::: simses.battery.derating.LinearVoltageDerating

::: simses.battery.derating.LinearThermalDerating
