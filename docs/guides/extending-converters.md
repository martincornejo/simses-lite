# Extending Converter Loss Models

How to implement a new converter loss characteristic as a [`ConverterLossModel`][simses.converter.converter.ConverterLossModel], drop it into a `Converter`, and plug it into the existing parameterised test suite.

!!! info "Who this is for"
    Researchers and engineers modelling a specific converter / inverter whose loss curve the shipped models don't cover. If you only need to pick between the existing options, see [Choosing a Converter Model](converter-models.md). For the system-level framing — the two-pass resolution and the AC/DC boundary — see [Converter concept](../concepts/converter.md).

## The contract

`ConverterLossModel` is a [`Protocol`][simses.converter.converter.ConverterLossModel] — no inheritance required; structural subtyping. Two methods, both operating on **normalised** power (p.u. of the converter's rated `max_power`, i.e. in `[-1, 1]`):

| Method | Argument | Returns |
|---|---|---|
| `ac_to_dc(power_norm)` | Normalised AC power | Normalised DC power |
| `dc_to_ac(power_norm)` | Normalised DC power | Normalised AC power |

Sign convention matches the rest of simses — positive = charging, negative = discharging.

`Converter` handles the W ↔ p.u. conversion on the outside, so your loss-model implementation never sees absolute power. This keeps the same loss curve valid across converter sizes (10 kW or 10 MW).

## The reciprocity requirement

`ac_to_dc` and `dc_to_ac` must be **exact inverses**: `dc_to_ac(ac_to_dc(p)) == p` for every `p`. The [two-pass resolution](../concepts/converter.md#the-two-pass-resolution) relies on this — when the downstream storage saturates, the converter back-converts the delivered DC power through `dc_to_ac` to recover the actual AC power. Approximate reciprocity silently drifts the reported AC value away from the truth.

For a **constant** efficiency, reciprocity is free: with fixed `eff`, `p · eff / eff = p`. For **power-dependent** efficiency it's subtle — evaluating `eff(|p_dc|)` inside `dc_to_ac` gives a different efficiency than `eff(|p_ac|)` used in `ac_to_dc`, and the pair drifts by several percent in the ramp region. See the inline comment in [`examples/extending/custom_loss_model.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_loss_model.py) for a walkthrough of the trap.

The robust workaround — used by both the shipped [`SinamicsS120`][simses.model.converter.sinamics.SinamicsS120] and the custom-loss-model example — is a lookup table built at construction.

## Worked walkthrough: two-segment efficiency

[`examples/extending/custom_loss_model.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_loss_model.py) implements a flat-plus-ramp efficiency curve: constant `eff_peak` above a `knee` normalised power, linearly ramping down to `eff_min` at zero. At construction it samples the curve into a 101-point LUT; both methods interpolate on the same table (with axes swapped for `dc_to_ac`), so they are exact inverses by construction.

Core structure:

```python
import numpy as np
from simses.interpolation import interp1d_scalar


class TwoSegmentEfficiency:
    def __init__(self, eff_peak=0.95, eff_min=0.5, knee=0.3, n_points=101):
        ac_pos = np.linspace(0, 1, n_points)
        eff = np.where(
            ac_pos >= knee,
            eff_peak,
            eff_min + (eff_peak - eff_min) * (ac_pos / knee),
        )
        dc_charge = ac_pos * eff                    # charging: DC = AC · eff
        ac_neg = -ac_pos[::-1]
        dc_discharge = ac_neg / eff[::-1]           # discharging: DC = AC / eff

        self._ac = np.concatenate([ac_neg[:-1], ac_pos]).tolist()
        self._dc = np.concatenate([dc_discharge[:-1], dc_charge]).tolist()

    def ac_to_dc(self, power_ac: float) -> float:
        return interp1d_scalar(power_ac, self._ac, self._dc)

    def dc_to_ac(self, power_dc: float) -> float:
        return interp1d_scalar(power_dc, self._dc, self._ac)
```

Key design points:

- The ``eff`` curve is defined once, **on the AC axis**, and sampled at construction. Both directions read the same `(ac, dc)` pairs — `dc_to_ac` just flips the lookup axes.
- The arrays are stitched into a single monotonically-increasing curve from −1 to +1, so `interp1d_scalar` (a scalar `bisect`-based helper from [`simses.interpolation`][simses.interpolation]) handles both signs.
- 101 sample points per direction is plenty for a smooth analytical curve; for noisy measured data you'd use more. The shipped `SinamicsS120` samples every 10th row of a 1001-point CSV.

Plug it into a `Converter` the same way as any shipped model:

```python
from simses.converter import Converter

converter = Converter(
    loss_model=TwoSegmentEfficiency(),
    max_power=100_000,     # W, rated
    storage=battery,
)
```

## When analytical inversion is tractable

If your loss curve has a closed-form inverse (e.g. a pure polynomial, or a fixed-efficiency model), you can skip the LUT and implement `ac_to_dc` / `dc_to_ac` directly as formulas — as the shipped [`FixedEfficiency`][simses.model.converter.fix_efficiency.FixedEfficiency] does. For anything messier (piecewise, fitted, or lookup-backed curves), the LUT pattern above is the reliable default.

## Testing with `ConverterModelSpec`

`tests/test_converter_models.py` runs a generic suite against every shipped model — zero-power yields zero, charging has losses, discharging has losses, monotonic in both directions, efficiency within `(0, 1)`, and — critically — `ac_to_dc(dc_to_ac(p)) ≈ p` within 0.1 % (the reciprocity check). Add your model by appending a `ConverterModelSpec` entry:

```python
# tests/test_converter_models.py
CONVERTER_SPECS: list[ConverterModelSpec] = [
    ConverterModelSpec(name="FixedEfficiency_95", factory=lambda: FixedEfficiency(0.95)),
    ConverterModelSpec(name="SinamicsS120", factory=SinamicsS120),
    ConverterModelSpec(name="SinamicsS120Fit", factory=SinamicsS120Fit),
    # --- your model below ---
    ConverterModelSpec(name="TwoSegmentEfficiency", factory=TwoSegmentEfficiency),
]
```

`factory` is any callable returning an instance — use a `lambda` to supply constructor args. Run the suite with `pytest tests/test_converter_models.py -v`.

## See Also

- [Converter concept](../concepts/converter.md) — the two-pass resolution and why reciprocity matters.
- [Choosing a Converter Model](converter-models.md) — the three shipped models as reference implementations.
- [`examples/extending/custom_loss_model.py`](https://github.com/tum-ees/simses/blob/main/examples/extending/custom_loss_model.py) — the full runnable walkthrough with the LUT construction.
- [`ConverterLossModel` API reference](../api/converter.md).
