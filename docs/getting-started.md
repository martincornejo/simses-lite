# Getting Started

A five-minute walkthrough: install simses and run a simple charge/discharge cycle.

## Prerequisites

- **Python 3.12 or newer** (required).
- **pip** or **[uv](https://docs.astral.sh/uv/)** (recommended — faster installs and built-in virtualenv management).

## Installation

```bash
pip install simses
```

Or with uv:

```bash
uv add simses
```

Quick import check:

```python
from simses.model.cell.sony_lfp import SonyLFP

cell = SonyLFP()                # 3 Ah, 3.2 V LFP cell (Sony/Murata US26650FTC1)
```

## Your first simulation

Build a 13-series pack of `SonyLFP` cells starting at 50 % SOC, and discharge it at 50 W for 30 minutes.

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 1),  # 13 serial, 1 parallel
    initial_states={"start_soc": 0.5, "start_T": 25.0},
)

dt = 60  # seconds per step

for _ in range(30):
    battery.step(-50.0, dt)   # negative = discharging

s = battery.state
print(f"SOC:         {s.soc:.3f}")
print(f"Terminal V:  {s.v:.2f} V")
print(f"Current:     {s.i:.2f} A")
print(f"Temperature: {s.T:.2f} °C")
print(f"Power:       {s.power:.2f} W")
```

Expected output:

```text
SOC:         0.303
Terminal V:  42.17 V
Current:     -1.19 A
Temperature: 25.00 °C
Power:       -50.00 W
```

!!! info "Sign convention"
    **Positive power/current = charging.** **Negative = discharging.** Applies uniformly across `Battery`, `Converter`, loss models, and every signed field of `BatteryState`. The `-1.18 A` above means the pack is actively delivering 1.18 A to the load during the last discharge step.

## Common pitfalls

!!! warning "Things that catch newcomers"
    - **`dt` is in seconds.** One minute is `dt=60`. Steps larger than a few minutes lose accuracy — power, SOC, and temperature dynamics need finer time resolution than that.
    - **Sign.** Passing `-5000` while meaning "charge at 5 kW" will discharge the battery and pin it at the SOC floor. If the output surprises you, check the sign.
    - **SOC pinned at a limit.** If `state.soc` stays flat at `1.0` or `0.0` across consecutive steps, the setpoint is being rejected by the SOC hard limit — lower the power or widen `soc_limits`.
    - **`initial_states` is required.** Minimum: `{"start_soc": ..., "start_T": ...}`. Omitting it raises `TypeError`.

## What to read next

- **Just learning the API** → the full [demo tutorial notebook](tutorials/demo.ipynb).
- **Running a study** → the [Concepts](concepts/battery.md) pages for understanding, then [User Guides](guides/installation.md) for applied recipes.
- **Extending simses** → one extension guide per subsystem: [cells](guides/extending-cells.md), [converters](guides/extending-converters.md), [degradation](guides/extending-degradation.md), [non-battery storage](guides/extending-storage.md).
