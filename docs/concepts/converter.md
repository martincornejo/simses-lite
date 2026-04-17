# Converter

How `Converter` couples an AC-side power setpoint to a DC-side storage, accounts for conversion losses, and reconciles what the storage could actually deliver.

!!! info "Who this is for"
    Applied users wiring a battery behind an AC power profile, and extenders writing new loss models. For the broader system picture see [Battery Model](battery.md) first.

## `Converter`, `ConverterLossModel`, and the storage

A simses converter is three things composed together: a **`Converter`**, a **`ConverterLossModel`**, and a **storage**.

[`ConverterLossModel`][simses.converter.converter.ConverterLossModel] is the **loss characteristic** of the AC/DC converter — the equivalent of the cell `CellType`: a stateless description of how input power becomes output power. It exposes two methods, `ac_to_dc(power_norm)` and `dc_to_ac(power_norm)`, both operating on *normalised* power in p.u. of the converter's rated `max_power`. Normalisation keeps the loss characteristic independent of sizing: the same [`FixedEfficiency`][simses.model.converter.fix_efficiency.FixedEfficiency] or [`SinamicsS120Fit`][simses.model.converter.sinamics.SinamicsS120Fit] model applies to a 10 kW or a 1 MW converter without change.

[`Converter`][simses.converter.converter.Converter] is the **simulator**. It owns the mutable [`ConverterState`][simses.converter.converter.ConverterState], handles denormalisation (W ↔ p.u.), clamps the AC setpoint to the rated power, and orchestrates one timestep against the storage. It also exposes the same `step(power, dt)` + `state.power` interface as `Battery`, which is what lets converters chain.

The **storage** is anything with a `step(power_setpoint, dt)` method and a `state.power` attribute — typically a [`Battery`][simses.battery.battery.Battery], but duck-typed so `Converter` itself fits the contract (see [Chaining](#chaining) below).

```python
from simses.converter import Converter
from simses.model.converter import FixedEfficiency

converter = Converter(
    loss_model=FixedEfficiency(0.95),  # the "loss characteristic"
    max_power=10_000,                   # rated AC power in W
    storage=battery,                    # anything with step() + state.power
)
```

Adding a new converter technology means writing a new `ConverterLossModel`, not touching `Converter`. See [Choosing a Converter Model](../guides/converter-models.md).

## What one step does

From the caller's perspective, a `Converter` exists to turn an AC-side power setpoint — the kind of thing a grid-scheduling algorithm or a dispatch optimiser emits — into a consistent battery-side command while keeping track of the losses in between.

A single `converter.step(power_setpoint, dt)` runs a small feedback loop:

1. **Start at the AC terminals.** The caller asks for some AC power, positive for charging or negative for discharging. The converter first limits this to its own rating — if the request is 15 kW but the converter is rated 10 kW, only 10 kW ever enters the loop.
2. **Cross the boundary into DC.** A real AC/DC converter dissipates some of the power it handles. When charging, less DC reaches the battery than was drawn from the AC side; when discharging, the battery must supply more DC than finally appears at the AC terminals. The loss model quantifies this.
3. **Ask the battery.** The DC power is handed to the storage, which advances its own state by one timestep. Crucially, the battery might not be able to honour the request — it may be at its voltage, SOC, thermal, or C-rate limit and accept or deliver less than commanded.
4. **Reconcile.** If the battery could not honour the DC request, the AC power the converter "thought" was crossing the terminals is no longer true. The converter therefore looks at what the battery *actually* delivered on the DC side and walks the loss model the other way — DC back to AC — to recover the AC power that really flowed. The losses are then computed at this true operating point.

The second direction of the loss model exists exactly for this reconciliation step. Without it, a battery that saturates would leave the converter reporting a fictional AC power and a wrong loss. The next section formalises this as the two-pass resolution.

## The two-pass resolution

```mermaid
flowchart TD
    A[AC setpoint in W] --> B[clamp to ±max_power]
    B --> C[ac_to_dc via loss model]
    C --> D[storage.step power_dc, dt]
    D --> E{|power_dc − storage.power|<br/>&gt; 1% of |power_dc|?}
    E -- no --> F[loss = power_ac − power_dc]
    E -- yes --> G[power_dc ← storage.power<br/>power_ac ← dc_to_ac power_dc]
    G --> F
    F --> H[write ConverterState]
```

1. **Clamp.** The AC setpoint is saturated into `[-max_power, max_power]`.
2. **Forward convert.** The clamped AC power becomes DC via `ac_to_dc`, and the storage is stepped with that DC command.
3. **Check.** If the storage's `state.power` differs from the commanded DC power by more than 1 %, the storage was limit-bound and the commanded value is discarded in favour of what the storage actually delivered.
4. **Back-convert.** The delivered DC power is run through `dc_to_ac` to find the AC power that actually crossed the terminals.
5. **Losses.** `loss = power_ac − power_dc` is written to `state.loss`, and `state.power` holds the reconciled AC value.

### Worked example

A `Converter` with `max_power = 10 kW` and `FixedEfficiency(0.95)` is asked to discharge at −10 kW while the underlying battery can only deliver −8 kW DC because of a voltage limit.

| Step | Quantity | Value |
|---|---|---|
| setpoint | $P_\mathrm{AC}^\mathrm{set}$ | −10 000 W |
| clamp | $P_\mathrm{AC}$ | −10 000 W |
| `ac_to_dc(−10 000)` | $P_\mathrm{DC}^\mathrm{cmd}$ | −10 526 W |
| `storage.step(−10 526, dt)` → `storage.state.power` | $P_\mathrm{DC}$ | −8 000 W |
| mismatch check | `|−10 526 − (−8 000)| / 10 526` | 24 % → recompute |
| `dc_to_ac(−8 000)` | $P_\mathrm{AC}$ | −7 600 W |
| losses | $P_\mathrm{AC} - P_\mathrm{DC}$ | 400 W |

`state.power_setpoint = −10 000`, `state.power = −7 600`, `state.loss = 400`. The caller sees immediately that less AC power was delivered than requested, and the loss is evaluated at the *delivered* operating point, not at the saturated one.

For `FixedEfficiency(0.95)` the forward and inverse maps are:

- Charging (power ≥ 0): $P_\mathrm{DC} = P_\mathrm{AC} \cdot \eta$, $P_\mathrm{AC} = P_\mathrm{DC} / \eta$.
- Discharging (power < 0): $P_\mathrm{DC} = P_\mathrm{AC} / \eta$, $P_\mathrm{AC} = P_\mathrm{DC} \cdot \eta$.

The asymmetric division is what makes $|P_\mathrm{DC}| > |P_\mathrm{AC}|$ during discharge: the battery must provide more DC than the converter delivers as AC, because the converter eats the difference.

## Sign convention

Positive = charging (power flows from the AC terminals into the storage), negative = discharging (power flows out). Applies to both AC and DC sides, and to the normalised values inside `ConverterLossModel`.

The loss is always non-negative: $|P_\mathrm{AC}| > |P_\mathrm{DC}|$ during charging (AC covers the loss on the way in), and $|P_\mathrm{DC}| > |P_\mathrm{AC}|$ during discharging (the storage covers the loss on the way out).

## Chaining

Because `Converter` exposes the same `step(power, dt)` + `state.power` contract that it requires of its storage, a `Converter` can wrap another `Converter`. This is how multi-stage topologies (e.g. MV/LV transformer + AC/DC inverter in series) are expressed:

```python
inner = Converter(loss_model=inner_model, max_power=500_000, storage=battery)
outer = Converter(loss_model=outer_model, max_power=500_000, storage=inner)

outer.step(power_ac, dt)  # propagates through both stages
```

The two-pass resolution still works at each level — if the innermost storage saturates, the limitation bubbles back up through each converter's back-conversion step.

## State

[`ConverterState`][simses.converter.converter.ConverterState] is a small dataclass:

| Field | Unit | Meaning |
|---|---|---|
| `power_setpoint` | W | The requested AC power, stored as given. |
| `power` | W | The AC power actually delivered (after clamping and any storage-limited back-conversion). |
| `loss` | W | Conversion loss this step, `power − power_dc`. Always ≥ 0. |

`state.power` is what you read when treating this `Converter` as another stage's storage — that's the hook that makes chaining work.

## Where to go next

- **Choosing a loss model:** [Choosing a Converter Model](../guides/converter-models.md).
- **Writing your own loss model:** [Extending converter models](../guides/converter-models.md#extending) — implement `ac_to_dc` and `dc_to_ac` on normalised power.
- **API reference:** [`Converter`][simses.converter.converter.Converter], [`ConverterLossModel`][simses.converter.converter.ConverterLossModel], [`ConverterState`][simses.converter.converter.ConverterState].
