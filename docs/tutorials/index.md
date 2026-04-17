# Tutorials

## Demo Notebook

[![Launch on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/tum-ees/simses/main?filepath=docs/tutorials/demo.ipynb)

The [demo notebook](demo.ipynb) is a self-contained tutorial that walks through
the main simses features with live code and plots.

### What You Will Learn

| Part | Topic | Key concepts |
|---|---|---|
| 1 | Battery Only | ECM simulation, SOC tracking, degradation |
| 2 | Battery + Converter | AC/DC conversion, Sinamics S120 efficiency curve, peak shaving |
| 3 | Two Strings | SOC-weighted power distribution, independent string tracking |
| 4 | Thermal Model | `AmbientThermalModel` coupling multiple strings, effective-cooling-area tuning |

### Prerequisites

- Python 3.12+ with simses installed
- Jupyter Notebook or JupyterLab

### Running Locally

```bash
# With uv (recommended)
uv sync --extra notebooks
uv run jupyter notebook docs/tutorials/demo.ipynb

# Or with pip
pip install "simses[notebooks]"
jupyter notebook docs/tutorials/demo.ipynb
```

### Estimated Time

Approximately 30–45 minutes to run and read through all four parts.
