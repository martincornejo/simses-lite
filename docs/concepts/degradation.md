# Degradation

How `DegradationModel` accumulates capacity fade and resistance rise over a simulation by composing a calendar aging model, a cyclic aging model, and a half-cycle detector.

!!! info "Who this is for"
    Applied users running multi-year studies where aging matters, and extenders fitting an aging law to new measurement data. If aging is out of scope for your study, `Battery(degradation=None)` simply skips this subsystem.

## `DegradationModel`, sub-models, and the cycle detector

A simses degradation setup is three things composed together.

[`DegradationModel`][simses.degradation.degradation.DegradationModel] is the **composer**. It owns the mutable [`DegradationState`][simses.degradation.state.DegradationState] (the running ledger of accumulated damage), holds a [`HalfCycleDetector`][simses.degradation.cycle_detector.HalfCycleDetector], and delegates the actual aging laws to two stateless sub-models. At each call to `Battery.step()` the battery hands the current `BatteryState` to `DegradationModel.step(state, dt)`, which applies calendar aging and — if a half-cycle has just completed — cyclic aging, then writes the updated `soh_Q` and `soh_R` back onto `BatteryState`.

[`CalendarDegradation`][simses.degradation.calendar.CalendarDegradation] and [`CyclicDegradation`][simses.degradation.cyclic.CyclicDegradation] are **protocols** — the aging-law equivalents of `CellType`: stateless, chemistry-specific descriptions of how damage accumulates under given stress. Concrete implementations are typically **(semi-)empirical fits** to accelerated-aging measurements on a specific cell — polynomial, Arrhenius, power-law, or lookup forms calibrated to observed fade curves, not first-principles electrochemistry. A `CalendarDegradation` exposes `update_capacity(state, dt, accumulated_qloss)` and `update_resistance(state, dt, accumulated_rinc)`; a `CyclicDegradation` exposes the same two methods but takes a `HalfCycle` instead of `dt`. Each call returns a *delta* (a non-negative increment), never an absolute value.

[`HalfCycleDetector`][simses.degradation.cycle_detector.HalfCycleDetector] is the **trigger**. It watches SOC across timesteps and raises a completed [`HalfCycle`][simses.degradation.cycle_detector.HalfCycle] whenever the SOC reverses direction. The `HalfCycle` carries the stress factors — depth of discharge, mean SOC, average C-rate, and full-equivalent-cycle contribution — that the cyclic model needs.

```python
from simses.degradation import DegradationModel
from simses.model.degradation import (
    SonyLFPCalendarDegradation,
    SonyLFPCyclicDegradation,
)

degradation = DegradationModel(
    calendar=SonyLFPCalendarDegradation(),
    cyclic=SonyLFPCyclicDegradation(),
    initial_soc=0.5,
)

battery = Battery(cell=SonyLFP(), circuit=(13, 2),
                  initial_states={"start_soc": 0.5, "start_T": 25.0},
                  degradation=degradation)
```

Cells that ship a default can skip the explicit construction: `Battery(..., degradation=True)` asks the `CellType` for its `default_degradation_model(initial_soc)`.

## Two SoH axes, two aging mechanisms

Aging in simses is tracked along two independent axes:

- **Capacity fade** — the cell holds less charge than when it was new. Represented by `state.soh_Q` (p.u., starts at 1.0, decreases). Scales the `capacity()` used by the `Battery` at every step.
- **Resistance rise** — the cell's internal resistance grows. Represented by `state.soh_R` (p.u., starts at 1.0, increases). Scales `internal_resistance()` at every step.

They are deliberately separate: at end-of-life for a stationary storage (typically 80 % capacity), the resistance may have grown by a factor of 1.5 or more, and the two decouple under different stress conditions. Downstream subsystems — the ECM quadratic, the hard limits, the losses — read the scaled quantities directly, so aging effects propagate automatically into voltage sag, efficiency loss, and thermal dissipation without any special handling.

Each axis has two contributions — calendar and cyclic — that accumulate independently in `DegradationState`:

| Field | Axis | Mechanism |
|---|---|---|
| `qloss_cal` | capacity | time + temperature + SOC (applies every step) |
| `qloss_cyc` | capacity | charge throughput (applies on each completed half-cycle) |
| `rinc_cal` | resistance | time + temperature + SOC |
| `rinc_cyc` | resistance | charge throughput |

At each step, `DegradationModel` sums the calendar contribution and — when the cycle detector triggers — the cyclic contribution, then writes the totals back onto the `BatteryState`.

## How one degradation step works

One call to `DegradationModel.step(state, dt)` runs two passes.

**Calendar pass (every step).** The calendar sub-model is asked for the capacity loss and resistance rise that accumulate over this timestep, given the current temperature and SOC. `DegradationModel` also hands it the current values of `qloss_cal` and `rinc_cal` — the calendar damage already accumulated — as `accumulated_qloss` and `accumulated_rinc`. The sub-model returns non-negative deltas, which are added to the accumulators and reflected on `state.soh_Q` and `state.soh_R`.

**Cyclic pass (on direction reversal).** The cycle detector is advanced with the new SOC. If it signals a completed half-cycle, the cyclic sub-model is called with the `HalfCycle` object and the current `qloss_cyc` / `rinc_cyc` accumulators. Again the sub-model returns deltas, which are added to the accumulators and reflected on `state.soh_Q` / `state.soh_R`. If no half-cycle completes this step, the cyclic pass is skipped entirely.

### Why the accumulator is passed in

Aging laws are typically nonlinear in their independent variable — calendar damage often grows as $\sqrt{t}$, $t^{0.75}$, or a double-exponential SEI form, and cyclic damage grows as $\sqrt{\text{FEC}}$ or a power law in charge throughput. Under *constant* stress these laws are straightforward to integrate. But in a real simulation, stress varies every timestep — temperature drifts, SOC swings, C-rate changes with operating profile — and a nonlinear law needs to know how much damage has already accumulated to compute the next increment correctly.

Passing `accumulated_qloss` / `accumulated_rinc` in as arguments lets the sub-model do this reconstruction on the fly without maintaining its own internal state. The `DegradationState` on `DegradationModel` is the *only* place aging state lives, which means checkpointing, warm-starting from a prior aging history, or swapping sub-models between runs all work without any coordination between the framework and the laws. Memoryless laws (e.g. linear-in-time calendar) are free to ignore the accumulators entirely.

The concrete example below walks through one common continuation technique — virtual-time reconstruction — as used by the Sony LFP calendar model.

## Concrete example: Sony LFP calendar aging (Naumann 2018)

[`SonyLFPCalendarDegradation`][simses.model.degradation.sony_lfp_calendar.SonyLFPCalendarDegradation] is a **semi-empirical** √t aging law fitted to accelerated-aging measurements of the Sony US26650FTC1 cell by Naumann et al. ([*Journal of Energy Storage*, 2018](https://doi.org/10.1016/j.est.2018.01.019)). It combines an Arrhenius temperature dependence with a cubic SOC dependence. Under constant stress $s$, capacity loss grows as:

$$
Q_\mathrm{loss}(t) \;=\; s(T, \mathrm{SOC}) \cdot \sqrt{t}
$$

The stress factor is

$$
s(T, \mathrm{SOC}) \;=\; k_\mathrm{ref} \cdot \exp\!\left(-\frac{E_a}{R}\left(\frac{1}{T} - \frac{1}{T_\mathrm{ref}}\right)\right) \cdot \bigl( C (\mathrm{SOC} - 0.5)^3 + D \bigr)
$$

Constants and coefficients come from Naumann 2018.

Because $T$ and SOC change every step, we can't just add $s \cdot \sqrt{\Delta t}$ to the running total — that would double-count time spent at earlier stress levels. Instead, the model inverts the law to find the **virtual time** that would have produced the current accumulated loss under the *current* stress:

$$
t_\mathrm{virt} \;=\; \left(\frac{Q_\mathrm{acc}}{s(T, \mathrm{SOC})}\right)^{\!2}
$$

and steps forward from there:

$$
\Delta Q \;=\; s(T, \mathrm{SOC}) \cdot \sqrt{t_\mathrm{virt} + \Delta t} \;-\; Q_\mathrm{acc}
$$

The result respects the past history (through $Q_\mathrm{acc}$) without any internal state in the sub-model. The cyclic counterpart [`SonyLFPCyclicDegradation`][simses.model.degradation.sony_lfp_cyclic.SonyLFPCyclicDegradation] — also a semi-empirical fit, from Naumann et al. ([*Journal of Power Sources*, 2020](https://doi.org/10.1016/j.jpowsour.2019.227666)) — follows the same shape with FEC replacing time: virtual-FEC reconstruction, stress factor depending on DoD and C-rate, triggered only on completed half-cycles.

Other aging laws (different exponents, Arrhenius-only, lookup-table stress factors, linear-in-FEC) use their own inversions or simpler integrators but follow the same stateless-sub-model contract.

## The half-cycle detector

[`HalfCycleDetector`][simses.degradation.cycle_detector.HalfCycleDetector] is a lightweight rainflow-style detector: it tracks SOC movement and finalises a half-cycle whenever the direction reverses.

Behaviour:

- **Rest periods (SOC unchanged)** contribute nothing to the cyclic bookkeeping. Calendar aging continues to apply via the calendar pass above.
- **First movement** establishes an initial direction but does not yet close a half-cycle.
- **Same direction** continues accumulating elapsed time and mean-SOC samples.
- **Direction reversal** closes the current half-cycle, emits a `HalfCycle`, and starts a new one from the turning point.

Each completed [`HalfCycle`][simses.degradation.cycle_detector.HalfCycle] carries four stress factors the cyclic model consumes:

| Field | Unit | Meaning |
|---|---|---|
| `depth_of_discharge` | p.u. | SOC swing magnitude $\lvert\Delta \mathrm{SOC}\rvert$ between reversals. |
| `mean_soc` | p.u. | Time-averaged SOC during the half-cycle. |
| `c_rate` | 1/h | Average C-rate during the half-cycle, $\mathrm{DoD} / \Delta t$. |
| `full_equivalent_cycles` | — | FEC contribution, $\mathrm{DoD} / 2$. |

## Composition patterns

The usual case is a symmetric setup — both legs active:

```python
DegradationModel(
    calendar=SonyLFPCalendarDegradation(),
    cyclic=SonyLFPCyclicDegradation(),
    initial_soc=0.5,
)
```

For a calendar-only or cyclic-only study (useful when decomposing an observed fade curve against an experiment), two factory methods on `DegradationModel` inject a no-op sub-model on the opposite leg:

```python
DegradationModel.calendar_only(SonyLFPCalendarDegradation(), initial_soc=0.5)
DegradationModel.cyclic_only(SonyLFPCyclicDegradation(), initial_soc=0.5)
```

To warm-start from a known aging history (e.g. a three-year pre-aging before the simulation proper), pass an explicit `DegradationState`:

```python
prior = DegradationState(qloss_cal=0.05, qloss_cyc=0.02)
DegradationModel(calendar=..., cyclic=..., initial_soc=0.5, initial_state=prior)
```

A law with virtual-time continuation (like Sony LFP) then picks up seamlessly from the prior accumulated loss.

## State

[`DegradationState`][simses.degradation.state.DegradationState] is a small dataclass — four non-negative p.u. accumulators:

| Field | Axis | Source |
|---|---|---|
| `qloss_cal` | capacity fade | calendar sub-model |
| `qloss_cyc` | capacity fade | cyclic sub-model |
| `rinc_cal` | resistance rise | calendar sub-model |
| `rinc_cyc` | resistance rise | cyclic sub-model |

The corresponding SoH values — `state.soh_Q` and `state.soh_R` on `BatteryState` — are always recoverable as $1 - q_\mathrm{loss}^\mathrm{cal} - q_\mathrm{loss}^\mathrm{cyc}$ and $1 + r_\mathrm{inc}^\mathrm{cal} + r_\mathrm{inc}^\mathrm{cyc}$ respectively.

## Where to go next

- **Writing your own aging model:** [Extending degradation](../guides/cell-models.md#extending) — implement `CalendarDegradation` or `CyclicDegradation`; the contract is two methods, no internal state.
- **Cell defaults:** the SonyLFP cell ships a default calendar+cyclic pair — see [Choosing a Cell Model](../guides/cell-models.md).
- **API reference:** [`DegradationModel`][simses.degradation.degradation.DegradationModel], [`DegradationState`][simses.degradation.state.DegradationState], [`CalendarDegradation`][simses.degradation.calendar.CalendarDegradation], [`CyclicDegradation`][simses.degradation.cyclic.CyclicDegradation], [`HalfCycleDetector`][simses.degradation.cycle_detector.HalfCycleDetector].
