"""State-logging pattern for simses simulations.

Demonstrates the recommended way to accumulate state across a run:

1. Pre-allocate numpy arrays keyed by each state field you care about.
2. Fill them inside the simulation loop (fast, no per-step allocations).
3. Wrap into a pandas DataFrame at the end for analysis or plotting.

This avoids two common pitfalls: deep-copying the mutable state object on
every step (slow, bloats memory) and appending to lists before converting
(quadratic in the number of steps for large runs).
"""

import numpy as np
import pandas as pd

from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP


def simulate(n_steps: int = 120, dt: float = 60.0) -> pd.DataFrame:
    """Run a symmetric charge/discharge cycle and return the logged state.

    Args:
        n_steps: Total number of timesteps (first half charge, second half
            discharge).
        dt: Seconds per step.

    Returns:
        DataFrame indexed by step number, one column per logged field.
    """
    battery = Battery(
        cell=SonyLFP(),
        circuit=(13, 1),
        initial_states={"start_soc": 0.5, "start_T": 25.0},
    )

    # Pre-allocate one array per field — cheap and keeps the loop free of
    # any Python-level allocations.
    fields = ("soc", "v", "i", "power", "loss", "T")
    log = {f: np.empty(n_steps) for f in fields}

    half = n_steps // 2
    profile = np.concatenate([np.full(half, 50.0), np.full(n_steps - half, -50.0)])

    for t, power in enumerate(profile):
        battery.step(power, dt)
        s = battery.state
        log["soc"][t] = s.soc
        log["v"][t] = s.v
        log["i"][t] = s.i
        log["power"][t] = s.power
        log["loss"][t] = s.loss
        log["T"][t] = s.T

    return pd.DataFrame(log)


def plot(df: pd.DataFrame) -> None:
    """Plot SOC, terminal voltage, current, and power over time.

    Uses matplotlib, which is in the ``notebooks`` optional-dependency
    group. Install with ``uv sync --extra notebooks`` (or
    ``uv sync --all-groups``).
    """
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex=True)
    df["soc"].plot(ax=axes[0, 0], title="SOC", ylabel="p.u.")
    df["v"].plot(ax=axes[0, 1], title="Terminal voltage", ylabel="V")
    df["i"].plot(ax=axes[1, 0], title="Current", ylabel="A")
    df["power"].plot(ax=axes[1, 1], title="Delivered power", ylabel="W")
    for ax in axes.flat:
        ax.set_xlabel("step")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    df = simulate()
    print(df.describe())
    try:
        plot(df)
    except ImportError:
        print("matplotlib not installed — skipping plot")
