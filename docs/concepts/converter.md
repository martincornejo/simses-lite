# Converter

The `Converter` class is an AC/DC converter wrapper that applies a loss model
before forwarding power to a storage system (e.g., `Battery`).

## Role of the Converter

[PLACEHOLDER: Explain the AC/DC boundary — what power is set at AC side, what reaches battery]

```
AC setpoint → loss model → DC power → Battery.update()
```

## Loss Models

A converter loss model implements two methods:

- `ac_to_dc(power_norm)` — converts normalized AC power to normalized DC power
- `dc_to_ac(power_norm)` — converts normalized DC power to normalized AC power

Power is normalized to the converter's rated `max_power`.

[PLACEHOLDER: Brief comparison table of available loss models]

## Power Clamping

[PLACEHOLDER: Explain how AC power is clamped to `max_power` before the loss model]

## Sign Convention

Same as battery: positive = charging (power flows into storage), negative = discharging.

## Composability

`Converter` wraps any storage object with an `update(power, dt)` method — it is
not tied to `Battery` specifically.

[PLACEHOLDER: Show a short code snippet composing Converter with Battery]

## See Also

- [Choosing a Converter Model](../guides/converter-models.md)
- [`Converter` API reference](../api/converter.md)
