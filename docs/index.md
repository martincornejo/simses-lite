# simses

**A Python simulator for battery energy storage systems (BESS).**

simses models battery systems using equivalent-circuit cells in series-parallel configurations, AC/DC converter loss models, calendar and cyclic degradation, and optional thermal environments. Every subsystem is an independent, composable piece — so the same API runs a cell-only study, a full converter-backed pack, or a containerised BESS with HVAC and solar loading. Primary focus is stationary storage, though the building blocks extend naturally to mobile battery applications.

## Install

```bash
pip install simses
```

Python 3.12 or newer is required. See [Getting Started](getting-started.md) for uv, dev, and docs setups.

## Quick-start

```python
from simses.battery import Battery
from simses.model.cell.sony_lfp import SonyLFP

battery = Battery(
    cell=SonyLFP(),
    circuit=(13, 1),                                    # 13 serial, 1 parallel
    initial_states={"start_soc": 0.5, "start_T": 298.15},
)

for _ in range(30):
    battery.step(-50.0, dt=60)   # discharge at 50 W, one minute per step

print(f"SOC: {battery.state.soc:.3f}, V: {battery.state.v:.2f}")
# SOC: 0.303, V: 42.17
```

## Where to go

- **New to simses.** → [Getting Started](getting-started.md) — a five-minute walkthrough.
- **Running a study.** → [Concepts](concepts/battery.md) for understanding the subsystems, [User Guides](guides/installation.md) for applied recipes.
- **Extending simses.** → start with the relevant [Concepts](concepts/battery.md) page; dedicated extension guides are in progress.
- **Full walkthrough.** → the interactive [demo tutorial notebook](tutorials/demo.ipynb).

## Contributing

Contributions are welcome. See the [Contributing guide](contributing.md) for development setup, test commands, and PR conventions.

## Citation

If you use simses in academic work, please cite the original SimSES paper:

> Möller, M., Kucevic, D., Collath, N., Parlikar, A., Dotzauer, P., Tepe, B., Englberger, S., Jossen, A., & Hesse, H. (2022). *SimSES: A holistic simulation framework for modeling and analyzing stationary energy storage systems.* Journal of Energy Storage, 49, 103743. [doi:10.1016/j.est.2021.103743](https://doi.org/10.1016/j.est.2021.103743)

## Acknowledgements

simses is a ground-up rewrite of the original [SimSES](https://gitlab.lrz.de/open-ees-ses/simses), developed at the TUM Chair of Electrical Energy Storage Technology (EES). This version builds directly on the models, data, and years of research from that project.

## License

BSD 3-Clause. Copyright © 2020–2026 TUM Chair of Electrical Energy Storage (EES).
