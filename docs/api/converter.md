# Converter API

The `simses.converter` module is one class plus one Protocol: the [`Converter`][simses.converter.converter.Converter] simulator and the [`ConverterLossModel`][simses.converter.converter.ConverterLossModel] protocol that loss curves satisfy. For the two-pass resolution, sign conventions, and the duck-typed storage contract, see the [Converter concept page](../concepts/converter.md).

## Converter

AC/DC converter that clamps to a rated power, applies a loss model, and forwards DC power to a downstream storage. Exposes the same `step(power, dt)` + `state.power` contract that it requires of its storage, so converters can chain.

::: simses.converter.converter.Converter

## Converter State

Mutable state written by each `Converter.step()` — AC setpoint, delivered AC power, and conversion loss.

::: simses.converter.converter.ConverterState

## Converter Loss Model Interface

Protocol that every loss model implements. Two methods operating on normalised power (p.u. of `max_power`); no inheritance required. See [Choosing a Converter Model](../guides/converter-models.md) for the shipped implementations and [Extending Converter Loss Models](../guides/extending-converters.md) for writing your own.

::: simses.converter.converter.ConverterLossModel
