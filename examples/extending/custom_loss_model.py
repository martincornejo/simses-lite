"""Two-segment efficiency converter loss model.

Demonstrates a :class:`~simses.converter.converter.ConverterLossModel`
implementation with a load-dependent efficiency: flat above a knee
(``0.3`` p.u. by default), linearly ramping down below it — a crude
approximation of real converters that are lossy at light load due to
fixed standby and switching losses.
"""

import numpy as np
import pandas as pd

from simses.battery import Battery
from simses.converter import Converter
from simses.interpolation import interp1d_scalar
from simses.model.cell.sony_lfp import SonyLFP


class TwoSegmentEfficiency:
    """Converter loss model with a flat-plus-ramp efficiency curve.

    For AC power magnitude ``|p|``:

    * ``|p| >= knee``: efficiency is ``eff_peak``.
    * ``|p| <  knee``: efficiency ramps linearly from ``eff_min`` at
      ``|p| = 0`` up to ``eff_peak`` at ``|p| = knee``.

    The curve is sampled into a lookup table at construction; both
    conversion methods interpolate on that table (with axes reversed for
    the inverse direction), so they are exact inverses.
    """

    def __init__(
        self,
        eff_peak: float = 0.95,
        eff_min: float = 0.5,
        knee: float = 0.3,
        n_points: int = 101,
    ) -> None:
        """
        Args:
            eff_peak: Efficiency (p.u.) in the flat high-load region.
            eff_min: Efficiency (p.u.) at zero load — the worst-case
                operating point.
            knee: Normalised power at which the ramp meets the flat.
            n_points: Number of samples per sign of the lookup table.
        """
        # Power-dependent efficiency breaks the naive "eff at |p|" trick:
        # the AC and DC sides sit at different magnitudes, so dc_to_ac
        # evaluated at eff(|p_dc|) is not the inverse of ac_to_dc
        # evaluated at eff(|p_ac|), and Converter's two-pass resolution
        # drifts. The fix (same pattern as SinamicsS120) is to sample the
        # curve once into a LUT and interpolate on it from both directions
        # — exact inverses by construction.
        ac_pos = np.linspace(0, 1, n_points)
        eff = np.where(
            ac_pos >= knee,
            eff_peak,
            eff_min + (eff_peak - eff_min) * (ac_pos / knee),
        )
        dc_charge = ac_pos * eff  # charging: DC = AC · eff

        ac_neg = -ac_pos[::-1]
        eff_neg = eff[::-1]
        dc_discharge = ac_neg / eff_neg  # discharging: DC = AC / eff

        # Stitch into a monotonically-increasing curve from -1 to +1.
        self._ac = np.concatenate([ac_neg[:-1], ac_pos]).tolist()
        self._dc = np.concatenate([dc_discharge[:-1], dc_charge]).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._ac, self._dc)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._dc, self._ac)


def simulate(dt: float = 60.0) -> pd.DataFrame:
    """Step a battery + converter through four power regimes and log the loss.

    The profile hits both sides of the knee and both signs:

    * 30 steps charging at 80 % of rated (flat high-load region).
    * 30 steps charging at 10 % of rated (below the knee — lossy regime).
    * 30 steps discharging at 80 % of rated.
    * 30 steps discharging at 10 % of rated.

    Returns:
        DataFrame with per-step ``setpoint``, ``ac_power``, and ``loss``.
    """
    battery = Battery(
        cell=SonyLFP(),
        circuit=(13, 10),  # 30 Ah, ~42 V nominal — sized so the converter never saturates
        initial_states={"start_soc": 0.5, "start_T": 25.0},
    )
    max_power = 1500.0
    converter = Converter(
        loss_model=TwoSegmentEfficiency(),
        max_power=max_power,
        storage=battery,
    )

    profile = np.concatenate([
        np.full(30, +0.8 * max_power),  # charge, flat region
        np.full(30, +0.1 * max_power),  # charge, ramp region
        np.full(30, -0.8 * max_power),  # discharge, flat region
        np.full(30, -0.1 * max_power),  # discharge, ramp region
    ])

    log: dict[str, list[float]] = {"setpoint": [], "ac_power": [], "loss": []}
    for setpoint in profile:
        converter.step(float(setpoint), dt)
        log["setpoint"].append(float(setpoint))
        log["ac_power"].append(converter.state.power)
        log["loss"].append(converter.state.loss)

    return pd.DataFrame(log)


if __name__ == "__main__":
    df = simulate()
    df["loss_frac"] = df["loss"] / df["setpoint"].abs()
    print(
        df
        .groupby(df.index // 30)["loss_frac"]
        .mean()
        .rename({
            0: "charge 80%",
            1: "charge 10%",
            2: "discharge 80%",
            3: "discharge 10%",
        })
    )
