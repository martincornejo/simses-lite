# Logging and Plots

A simses simulation runs in place: every `step()` mutates the state, overwriting the previous timestep's values. If you want to analyse or plot anything across time, collect the state into an external log yourself.

This guide shows the recommended pattern — accumulate per-field arrays in the loop, wrap into a `pandas.DataFrame` at the end — and a minimal matplotlib recipe. The canonical reference is [`examples/state_logging.py`](https://github.com/tum-ees/simses/blob/main/examples/state_logging.py).

## The logging loop

Two interchangeable variants — pick whichever reads clearer for your loop.

**Lists + DataFrame** (shortest to write, no upfront size needed):

```python
import pandas as pd

log = {"time": [], "soc": [], "v": [], "i": [], "power": [], "loss": [], "T": []}

for t in range(n_steps):
    battery.step(power[t], dt)
    s = battery.state
    log["time"].append(t * dt)
    log["soc"].append(s.soc)
    log["v"].append(s.v)
    log["i"].append(s.i)
    log["power"].append(s.power)
    log["loss"].append(s.loss)
    log["T"].append(s.T)

df = pd.DataFrame(log)
```

**Pre-allocated numpy arrays** (fastest for very long runs):

```python
import numpy as np

fields = ("soc", "v", "i", "power", "loss", "T")
log = {"time": np.arange(n_steps) * dt} | {f: np.empty(n_steps) for f in fields}

for t in range(n_steps):
    battery.step(power[t], dt)
    s = battery.state
    log["soc"][t] = s.soc
    log["v"][t] = s.v
    log["i"][t] = s.i
    log["power"][t] = s.power
    log["loss"][t] = s.loss
    log["T"][t] = s.T

df = pd.DataFrame(log)
```

The time column is in seconds (matching `dt`) and stays as a regular column — call `df.set_index("time")` if you prefer it as the DataFrame index. For plotting over long horizons, divide to hours or days on the way out — `df["time"] / 3600`, `df["time"] / 86400`.

For typical simulations (tens of thousands of steps) the two perform indistinguishably. The numpy variant reduces per-step Python overhead noticeably for million-step runs.

## A reusable logger class

Inlining the per-step assignments reads fine for a one-off script. For longer pipelines, or when several scripts share the same field set, a thin wrapper pays for itself — it encapsulates the allocation, the indexing, and the DataFrame conversion:

```python
import numpy as np
import pandas as pd


class SimulationLog:
    """Pre-allocated per-step log backed by numpy arrays.

    A ``time`` column is auto-populated from ``n_steps`` and ``dt``, so
    callers only need to pass the state fields to :meth:`log`.
    """

    def __init__(self, n_steps: int, dt: float, fields: list[str]) -> None:
        self.data = {"time": np.arange(n_steps) * dt}
        self.data.update({f: np.full(n_steps, np.nan) for f in fields})

    def log(self, index: int, **values: float) -> None:
        for key, value in values.items():
            self.data[key][index] = value

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.data)


log = SimulationLog(n_steps, dt=dt, fields=["soc", "v", "i", "power", "loss", "T"])

for t in range(n_steps):
    battery.step(power[t], dt)
    s = battery.state
    log.log(t, soc=s.soc, v=s.v, i=s.i, power=s.power, loss=s.loss, T=s.T)

df = log.to_dataframe()
```

Initialising every entry to `np.nan` gives you a visible sentinel — unfilled rows (e.g. from a partial run that crashed) show up as missing rather than silently zero.

For a known system layout — multi-string packs, systems with HVAC and solar drivers, etc. — subclass the logger to hide the per-component bookkeeping:

```python
class MultiStringLog(SimulationLog):
    def __init__(self, n_steps: int, dt: float, strings) -> None:
        self.strings = strings
        fields = ["total_power", "avg_soc"]
        for i, _ in enumerate(strings):
            fields += [f"s{i}_soc", f"s{i}_power"]
        super().__init__(n_steps, dt, fields)

    def log(self, index: int) -> None:                         # type: ignore[override]
        socs = [bat.state.soc for bat, _ in self.strings]
        self.data["total_power"][index] = sum(c.state.power for _, c in self.strings)
        self.data["avg_soc"][index] = sum(socs) / len(socs)
        for i, (bat, conv) in enumerate(self.strings):
            self.data[f"s{i}_soc"][index] = bat.state.soc
            self.data[f"s{i}_power"][index] = conv.state.power
```

The simulation loop reduces to `log.log(t)` with no fields to remember at the call site — the subclass knows the system's layout. See [Multi-String Systems](multi-string.md) for the matching `strings = [(Battery, Converter), ...]` pattern.

## What to avoid

- **Deep-copying the state every step.** `log.append(copy.deepcopy(battery.state))` works, but it allocates a fresh dataclass on every step and leaves you with an awkward `log[i].soc` instead of `df["soc"]`.
- **`np.append` in a loop.** Unlike `list.append`, `np.append` rebuilds the whole array each call — quadratic in the number of steps.

## Plotting

matplotlib lives in the `notebooks` optional-dependency group — install with `uv sync --extra notebooks` (or `--all-groups`, which pulls it transitively).

A minimal 2×2 grid of SOC, terminal voltage, current, and delivered power:

```python
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True)
df.plot(x="time", y="soc",   ax=axes[0, 0], title="SOC",              ylabel="p.u.", legend=False)
df.plot(x="time", y="v",     ax=axes[0, 1], title="Terminal voltage", ylabel="V",    legend=False)
df.plot(x="time", y="i",     ax=axes[1, 0], title="Current",          ylabel="A",    legend=False)
df.plot(x="time", y="power", ax=axes[1, 1], title="Delivered power",  ylabel="W",    legend=False)
for ax in axes.flat:
    ax.set_xlabel("time [s]")
fig.tight_layout()
plt.show()
```

For richer plotting — heatmaps, combined axes, aging curves across many years — the [demo tutorial notebook](../tutorials/demo.ipynb) is a more substantial starting point.

## Coarse-interval logging for long runs

Degradation studies often cover years of simulated time at 1-minute (or finer) timesteps. Logging every step becomes memory-heavy and mostly redundant — SoH moves slowly, so logging hourly or daily is sufficient. Just guard the append behind a modulo check:

```python
log_every = 60  # once per hour if dt = 60 s
rows: list[dict] = []

for t in range(n_steps):
    battery.step(power[t], dt)
    if t % log_every == 0:
        rows.append({
            "time": t * dt,
            "soh_Q": battery.state.soh_Q,
            "soh_R": battery.state.soh_R,
            "soc": battery.state.soc,
        })

df = pd.DataFrame(rows)
```

A list of dicts scales to a `DataFrame` naturally via `pd.DataFrame(rows)` and keeps the row schema explicit per entry.

## See Also

- [`examples/state_logging.py`](https://github.com/tum-ees/simses/blob/main/examples/state_logging.py) — the canonical reference for this pattern; used as the integration test.
- [Demo tutorial notebook](../tutorials/demo.ipynb) — richer plotting and multi-subsystem logging.
- [Battery state](../concepts/battery.md#state) — the full list of `BatteryState` fields you can log.
