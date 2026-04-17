# Thermal API

The `simses.thermal` module provides two environment models — a simple ambient coupling and a physics-based container with walls + HVAC + solar — wired through the [`ThermalComponent`][simses.thermal.protocol.ThermalComponent] structural protocol. For the thermal network, protocol contract, and the HVAC strategy/hardware split, see the [Thermal Models concept page](../concepts/thermal.md).

## Thermal component protocol

Structural contract that any registerable node (battery, non-battery storage, custom component) must satisfy: `state.T`, `state.heat`, `thermal_capacity`, `thermal_resistance`.

::: simses.thermal.protocol.ThermalComponent

## Ambient thermal model

Zero-dimensional environment: each registered component is an independent node coupled to a single ambient temperature. Use when the thermal environment can be treated as a uniform external temperature (bench tests, climate-controlled rooms, first-order sanity checks).

::: simses.thermal.ambient.AmbientThermalModel

::: simses.thermal.ambient.AmbientThermalState

## Container thermal model

Physics-based BESS container with five coupled thermal nodes (batteries, internal air, three wall layers), HVAC injection at the air node, and optional solar heat on the outer wall. Use when wall conduction, air thermal mass, HVAC sizing, or diurnal external cycles matter.

::: simses.thermal.container.ContainerThermalModel

::: simses.thermal.container.ContainerThermalState

::: simses.thermal.container.ContainerProperties

::: simses.thermal.container.ContainerLayer

## HVAC

Hardware-side Protocol converting a thermal-power demand into the corresponding electrical draw. The shipped constant-COP implementation is a reasonable default; swap it for a detailed chiller model by implementing the same two-method interface.

::: simses.thermal.container.HvacModel

::: simses.thermal.container.ConstantCopHvac

## Thermal management strategies

The "brain" side of the HVAC: decides how much heating/cooling the container needs per step. Use `ThermostatStrategy` for simple hysteresis control, or `ExternalThermalManagement` as a pass-through when an external controller (MPC, optimisation, co-simulation) computes the demand upstream.

::: simses.thermal.container.ThermalManagementStrategy

::: simses.thermal.container.ThermostatStrategy

::: simses.thermal.container.ThermostatMode

::: simses.thermal.container.ExternalThermalManagement

## Solar heat load

Vectorised pre-computation of absorbed solar power on a container's outer walls. Takes a GHI time series, solar-position + Reindl decomposition + per-face geometry, and returns a per-timestep power series to feed `ContainerThermalModel.Q_solar`.

::: simses.thermal.solar.SolarConfig

::: simses.thermal.solar.solar_heat_load
