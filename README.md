# simses

[![PyPI](https://img.shields.io/pypi/v/simses)](https://pypi.org/project/simses/)
[![Python](https://img.shields.io/pypi/pyversions/simses)](https://pypi.org/project/simses/)
[![CI](https://github.com/tum-ees/simses/actions/workflows/ci.yml/badge.svg)](https://github.com/tum-ees/simses/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/pypi/l/simses)](LICENSE)

`simses` is a Python simulator for battery energy storage systems (BESS). It models battery systems
with equivalent-circuit cells, AC/DC converters, thermal behavior, and aging — for researchers
and engineers working on storage applications, sizing studies, operating strategies, and
techno-economic analysis.

It is designed to be simple, modular, and composable: a lightweight core that is easy to read,
extend, and integrate into your own simulations.

## Installation

Requires Python 3.12+.

```bash
pip install simses
```

## Development

We recommend [uv](https://docs.astral.sh/uv/) for managing the development environment:

```bash
git clone https://github.com/tum-ees/simses.git
cd simses
uv sync
```

We use `pytest` for testing and `ruff` for linting and formatting:

```bash
uv run pytest
```

## Citation

If you use `simses` in academic work, please cite the original SimSES paper:

> Möller, M., Kucevic, D., Collath, N., Parlikar, A., Dotzauer, P., Tepe, B., Englberger, S.,
> Jossen, A., & Hesse, H. (2022). SimSES: A holistic simulation framework for modeling and
> analyzing stationary energy storage systems. *Journal of Energy Storage*, 49, 103743.
> https://doi.org/10.1016/j.est.2021.103743

## Acknowledgements

`simses` is a ground-up rewrite of the original
[simses](https://gitlab.lrz.de/open-ees-ses/simses), developed at the Chair of Electrical Energy
Storage Technology (EES) at the Technical University of Munich. This version builds directly on the
models, data, and years of research from that project.

## License

See [LICENSE](LICENSE).
