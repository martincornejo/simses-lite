# Choosing an Aging Model

simses ships three (calendar, cyclic) aging model pairs today, each fitted to a specific commercial cell. The table below is the quick chooser; each pair is then documented in its own section with its underlying source, tested stressor envelope, and composition example.

!!! info "Who this is for"
    Users running multi-year studies where aging matters. Aging in simses is a **choice** — the electrical cell model and the aging model are composed independently, so you can pair any degradation pair with any `CellType` that shares the same chemistry family. For the framework itself, see [Degradation](../concepts/degradation.md).

## Comparison

| Pair | Chemistry | Tested cell | Format | Capacity | Trained DoD (cycling) | Trained T (cycling) | Ships as default of |
|---|---|---|---|---|---|---|---|
| [Naumann](#naumann-sony-lfp) | LFP | Sony US26650FTC1 | Cylindrical 26650 | 3 Ah | 10 – 90 % | 0 – 60 °C | `SonyLFP` |
| [Gasper LFP&#124;Gr](#gasper-lfpgr) | LFP (large-format) | Anonymised, ~2019 vintage | Prismatic | 250 Ah | 80 – 100 % | 10 – 45 °C | — (compose explicitly) |
| [Gasper NMC&#124;Gr B1](#gasper-nmcgr-b1) | NMC (large-format) | Anonymised, ~2020 vintage | Pouch | 50 Ah | 80 – 100 % | 10 – 45 °C | — (compose explicitly) |

All three pairs share simses's [`CalendarDegradation`][simses.degradation.calendar.CalendarDegradation] + [`CyclicDegradation`][simses.degradation.cyclic.CyclicDegradation] Protocol interface, so they slot interchangeably into a [`DegradationModel`][simses.degradation.degradation.DegradationModel].

## Naumann (Sony LFP)

The default aging pair shipped with `SonyLFP`. Semi-empirical fits to accelerated-aging tests on the Sony/Murata US26650FTC1 3 Ah cylindrical LFP cell:

- **Calendar** — √t stress-factor with Arrhenius temperature dependence and a cubic SOC term.
- **Cyclic** — √FEC stress-factor with a cubic DoD term and a linear C-rate term.

Both use exact virtual-time / virtual-FEC continuation so they stay correct under varying operating conditions. Best-suited to small-format cylindrical LFP and to any study where you want simses's ready-made "aging on" behaviour via `Battery(..., degradation=True)`. See [Degradation concept](../concepts/degradation.md#concrete-example-sony-lfp-calendar-aging-naumann-2018) for the worked walkthrough.

Sources: Naumann et al., [*J. Energy Storage* 17 (2018)](https://doi.org/10.1016/j.est.2018.01.019); [*J. Power Sources* 451 (2020)](https://doi.org/10.1016/j.jpowsour.2019.227666).

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 1),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=True,  # picks up the Naumann pair automatically
)
```

## Gasper LFP&#124;Gr

A large-format prismatic LFP capacity-fade model from Gasper et al. 2023 ([*J. Energy Storage* 73, 109042](https://doi.org/10.1016/j.est.2023.109042)), ported one-to-one from NREL's [BLAST-Lite](https://github.com/NREL/BLAST-Lite). Semi-empirical: an Arrhenius calendar term with anode-potential SoC dependence, and a low-order semi-empirical cyclic term. Behaves cleanly across the full DoD range (LFP chemistry is intrinsically DoD-insensitive in this fit).

!!! warning "Applicability caveat"
    The fit corresponds to a specific ~2019-vintage 250 Ah prismatic LFP cell (anonymised in the paper). Modern (2023 +) large-format LFP cells for stationary storage — CATL LF280K, EVE LF280K, BYD blade — typically show **2 – 3× longer cycle life** and comparable calendar life. Treat quantitative EOL predictions from this model as **conservative lower bounds**. The *shape* of the aging response (SoC / T / DoD / C-rate sensitivities) remains useful for aging-aware operation studies.

!!! note "No resistance model"
    Gasper et al. 2023 publishes capacity-fade equations only. `update_resistance()` returns 0 on both legs — `state.soh_R` stays at 1.0 for the whole simulation. If your study depends on resistance rise, combine with a separate resistance-only calendar or cyclic sub-model, or use the Naumann pair.

**Recommended pairing.** Compose with the existing [`SonyLFP`](cell-models.md#sonylfp) electrical model as an LFP-chemistry proxy. OCV, hysteresis, and entropy are chemistry properties and transfer cleanly across cell formats; capacity is scaled to system level via `circuit=(s, p)`. Users who need a genuinely different capacity or a different R_int(SoC, T) map should subclass `SonyLFP` and override — see [Extending Cell Models](extending-cells.md).

```python
from simses.battery import Battery
from simses.degradation import DegradationModel
from simses.model.cell.sony_lfp import SonyLFP
from simses.model.degradation.gasper_lfp_gr_calendar import GasperLFPGrCalendar
from simses.model.degradation.gasper_lfp_gr_cyclic import GasperLFPGrCyclic

battery = Battery(
    cell=SonyLFP(),  # LFP-chemistry electrical proxy
    circuit=(1, 100),  # scale to system size
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=DegradationModel(
        calendar=GasperLFPGrCalendar(),
        cyclic=GasperLFPGrCyclic(),
        initial_soc=0.5,
    ),
)
```

## Gasper NMC&#124;Gr B1

A large-format pouch NMC capacity-fade model from the same Gasper et al. 2023 study. Compact single-term multiplicative power law in DoD, T, and C-rate — the simplest and best-behaved of the paper's four NMC chemistries. Monotonic in every stressor, no `abs()` clipping, extrapolates cleanly outside the [0.8, 1] DoD training band.

!!! warning "Applicability caveat"
    The fit corresponds to a specific ~2020-vintage 50 Ah pouch NMC|Gr cell (anonymised in the paper). Manufacturer-specific behaviour of modern large-format NMC|Gr cells will differ; treat quantitative EOL predictions from this model as approximate.

!!! note "No resistance model"
    Same as LFP|Gr — the Gasper paper publishes capacity fade only. `update_resistance()` returns 0 on both legs.

**Recommended pairing.** Compose with the existing [`Samsung94AhNMC`](cell-models.md#samsung94ahnmc) electrical model as an NMC-chemistry proxy.

```python
from simses.battery import Battery
from simses.degradation import DegradationModel
from simses.model.cell.samsung94Ah_nmc import Samsung94AhNMC
from simses.model.degradation.gasper_nmc_gr_b1_calendar import GasperNMCGrB1Calendar
from simses.model.degradation.gasper_nmc_gr_b1_cyclic import GasperNMCGrB1Cyclic

battery = Battery(
    cell=Samsung94AhNMC(),  # NMC-chemistry electrical proxy
    circuit=(96, 1),
    initial_states={"start_soc": 0.5, "start_T": 25.0},
    degradation=DegradationModel(
        calendar=GasperNMCGrB1Calendar(),
        cyclic=GasperNMCGrB1Cyclic(),
        initial_soc=0.5,
    ),
)
```

## Why "electrical model as a chemistry proxy"?

The Gasper cells in the paper are anonymised — the authors publish the aging fits but not the OCV curves, R_int maps, hysteresis, thermal properties, or mass. Building dedicated `GasperLFPGrCell` / `GasperNMCGrB1Cell` classes would require inventing values for everything except capacity, nominal voltage, and a single scalar DCIR from Table 1 of the paper. simses deliberately avoids that: the aging model is exported as a pair of Protocol implementations, and users pair it with whichever electrical cell model most closely matches the chemistry of interest.

The physical rationale is that **OCV(SoC), hysteresis, and entropy are chemistry properties** — they're a function of the electrode materials, not of the cell format. The LFP OCV plateau near 3.3 V, the entropic-coefficient signature, the small hysteresis at 50 % SOC — all of these transfer cleanly from a 3 Ah Sony cylindrical to a 250 Ah prismatic LFP cell of the same chemistry family. What *doesn't* transfer is R_int in Ohms (scales with capacity and format), max C-rates, thermal mass, and cell format geometry. If any of those matter to your study, subclass the electrical cell class and override the relevant properties.

## Attribution

The two Gasper pairs are ported from NREL's [BLAST-Lite](https://github.com/NREL/BLAST-Lite) Python library (BSD-3-Clause). Original implementations by Paul Gasper (NREL). Each ported file preserves the BLAST-Lite license notice in-file as required by BSD-3.

## Extending

To add a new aging model — either a fresh fit or a refit of an existing functional form against your own data — see [Extending Degradation](extending-degradation.md).

## See Also

- [Degradation concept](../concepts/degradation.md) — SoH axes, running totals, virtual-time continuation.
- [Choosing a Cell Model](cell-models.md) — electrical models recommended for pairing with the aging pairs above.
- [Models API reference](../api/models.md) — the shipped degradation model classes.
