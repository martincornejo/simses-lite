# Battery Model

The `Battery` class is the top-level battery system. It models a series-parallel
circuit of cells using an equivalent circuit model (ECM).

## Equivalent Circuit Model

[PLACEHOLDER: Explain the ECM — open-circuit voltage (OCV) and internal resistance (Rint)]

The ECM represents each cell as:

```
V_terminal = OCV(SOC, T) - I × Rint(SOC, T)
```

## Series-Parallel Circuit

[PLACEHOLDER: Explain how `(serial, parallel)` scales cell quantities to system quantities]

!!! info
    System voltage = cell voltage × `serial`  
    System capacity = cell capacity × `parallel`

## Step Cycle

Each call to `battery.step(power, dt)`:

1. Computes equilibrium current from power setpoint via the ECM quadratic formula
2. Applies hard current limits (C-rate, voltage, SOC)
3. Optionally applies linear voltage derating
4. Updates SOC and terminal voltage

[PLACEHOLDER: Add diagram of the update cycle]

## Sign Convention

- **Positive power / current = charging**
- **Negative power / current = discharging**

## State

All mutable battery state is stored in `BatteryState`:

[PLACEHOLDER: List key state fields — soc, voltage, current, temperature, soh]

## See Also

- [Choosing a Cell Model](../guides/cell-models.md)
- [`Battery` API reference](../api/battery.md)
