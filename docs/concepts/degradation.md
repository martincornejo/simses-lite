# Degradation

simses models battery aging through calendar and cyclic degradation mechanisms
that reduce the cell's state of health (SoH) over time.

## State of Health

[PLACEHOLDER: Explain SoH as a fraction of original capacity, range 0–1]

## Calendar Degradation

Calendar degradation accumulates as a function of time, temperature, and SOC —
even when the battery is idle.

[PLACEHOLDER: Describe the calendar degradation model for SonyLFP]

## Cyclic Degradation

Cyclic degradation accumulates with charge throughput. A half-cycle detector
tracks charge and discharge half-cycles using the rainflow counting algorithm.

[PLACEHOLDER: Describe the cyclic degradation model and half-cycle detection]

## Combining Models

`DegradationModel` is an ABC. Multiple degradation effects can be summed by
providing a list of models to `Battery`.

[PLACEHOLDER: Show code snippet composing calendar + cyclic degradation]

## See Also

- [`Degradation` API reference](../api/degradation.md)
- [SonyLFP model](../api/models.md)
