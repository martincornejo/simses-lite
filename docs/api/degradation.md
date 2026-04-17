# Degradation API

The `simses.degradation` module composes a calendar and cyclic aging sub-model with a half-cycle detector into a single [`DegradationModel`][simses.degradation.degradation.DegradationModel] that `Battery` steps every timestep. For the SoH split, statelessness rule, and virtual-time continuation, see the [Degradation concept page](../concepts/degradation.md).

## Degradation model

Composer for the two sub-models. Owns the `DegradationState` accumulators and runs the calendar pass every step, plus a cyclic pass each time a half-cycle completes. Provides `calendar_only` / `cyclic_only` factories for isolated studies.

::: simses.degradation.degradation.DegradationModel

## Degradation state

Non-negative p.u. accumulators for calendar and cyclic capacity fade and resistance rise. The only place aging state lives — sub-models are stateless.

::: simses.degradation.state.DegradationState

## Calendar degradation

Protocol for time-based aging laws (T, SOC, time). Every timestep receives the running `accumulated_qloss` so non-linear laws can continue correctly under varying stress. See [Extending Degradation Models](../guides/extending-degradation.md).

::: simses.degradation.calendar.CalendarDegradation

## Cyclic degradation

Protocol for throughput-based aging laws. Called on each completed half-cycle with a `HalfCycle` object carrying the stress factors.

::: simses.degradation.cyclic.CyclicDegradation

## Cycle detection

Rainflow-style detector that watches SOC across timesteps and emits a `HalfCycle` whenever the direction reverses. Drives the cyclic pass.

::: simses.degradation.cycle_detector.HalfCycleDetector

::: simses.degradation.cycle_detector.HalfCycle
