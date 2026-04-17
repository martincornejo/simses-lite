"""Integration tests for the scripts under ``examples/``.

Each test imports the example module and exercises its ``simulate()``
(or similarly-named) entry point end-to-end, touching multiple simses
subsystems at once. These guard against example code drifting out of
sync with the public API — a rewrite of `Battery`, `Converter`, etc.
that breaks an example will fail a test immediately rather than
silently rot a user-facing snippet.
"""

import pandas as pd
import pytest

from examples.extending.custom_cell import simulate as simulate_custom_cell
from examples.extending.custom_loss_model import (
    TwoSegmentEfficiency,
)
from examples.extending.custom_loss_model import (
    simulate as simulate_custom_loss_model,
)
from examples.state_logging import simulate as simulate_state_logging


def test_state_logging():
    df = simulate_state_logging(n_steps=60, dt=60.0)

    # Shape and schema.
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 60
    assert set(df.columns) == {"soc", "v", "i", "power", "loss", "T"}

    # No NaNs anywhere — catches uninitialised state or divergent physics.
    assert not df.isna().any().any()

    # Physical invariants of the example's charge-then-discharge profile.
    assert df["soc"].between(0.0, 1.0).all()
    assert (df["loss"] >= 0).all()
    mid = len(df) // 2
    assert df["soc"].iloc[mid - 1] > df["soc"].iloc[0]  # charge phase raises SOC
    assert df["soc"].iloc[-1] < df["soc"].iloc[mid - 1]  # discharge phase lowers SOC

    # No thermal model is attached, so temperature must stay at its initial value.
    assert (df["T"] == df["T"].iloc[0]).all()


def test_custom_cell():
    df = simulate_custom_cell(n_steps=60, dt=60.0)

    # Shape and schema.
    assert len(df) == 60
    assert set(df.columns) == {"soc", "v", "i", "power"}

    # No NaNs.
    assert not df.isna().any().any()

    # Invariants of a pure-discharge run on a linear-OCV cell.
    assert df["soc"].diff().iloc[1:].lt(0).all()  # SOC strictly decreases
    assert (df["i"] < 0).all()  # current stays in discharge
    assert (df["v"] > 0).all()  # terminal voltage positive
    assert df["v"].iloc[-1] < df["v"].iloc[0]  # voltage sags as SOC drops


def test_custom_loss_model_inverse_exact():
    """The LUT construction must make ac_to_dc and dc_to_ac exact inverses."""
    loss = TwoSegmentEfficiency()
    for p in (-0.9, -0.5, -0.15, -0.05, 0.05, 0.15, 0.5, 0.9):
        assert loss.dc_to_ac(loss.ac_to_dc(p)) == pytest.approx(p, abs=1e-6)
        assert loss.ac_to_dc(loss.dc_to_ac(p)) == pytest.approx(p, abs=1e-6)


def test_custom_loss_model():
    df = simulate_custom_loss_model(dt=60.0)

    # Shape and schema.
    assert len(df) == 120
    assert set(df.columns) == {"setpoint", "ac_power", "loss"}

    # No NaNs.
    assert not df.isna().any().any()

    # Loss is always non-negative.
    assert (df["loss"] >= 0).all()

    # Light-load fractional loss must exceed high-load fractional loss in
    # both directions — the defining property of the two-segment curve.
    loss_frac = df["loss"] / df["setpoint"].abs()
    charge_high = loss_frac.iloc[0:30].mean()
    charge_low = loss_frac.iloc[30:60].mean()
    discharge_high = loss_frac.iloc[60:90].mean()
    discharge_low = loss_frac.iloc[90:120].mean()
    assert charge_low > charge_high
    assert discharge_low > discharge_high
