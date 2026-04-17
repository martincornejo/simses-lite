# Installation

## Requirements

- **Python 3.12 or newer.** simses uses 3.12-only type syntax (PEP 604 `X | Y` unions, PEP 695 type aliases) at import time. Python 3.11 and earlier will fail immediately.
- A package manager: **pip** or **[uv](https://docs.astral.sh/uv/)** (recommended — faster resolution, built-in virtualenv management).

## Install from PyPI

```bash
pip install simses
```

Or with uv:

```bash
uv add simses
```

## Install from source

```bash
git clone https://github.com/tum-ees/simses.git
cd simses
uv sync
```

`uv sync` resolves and installs the runtime dependencies (numpy, pandas, scipy) into a local `.venv/`. For development, testing, or documentation work, add the relevant group:

| Command | Adds |
|---|---|
| `uv sync --group dev` | `pytest`, `ruff`, `codespell` |
| `uv sync --group docs` | `mkdocs`, `mkdocs-material`, `mkdocstrings`, `mkdocs-jupyter` |
| `uv sync --extra notebooks` | `jupyter`, `matplotlib`, `tqdm` (for running the example notebooks) |

Or install everything at once with `uv sync --all-groups` — the `docs` group pulls the `notebooks` extra transitively.

## Verify the install

```python
from simses.model.cell.sony_lfp import SonyLFP

cell = SonyLFP()
print(cell.electrical.nominal_capacity, "Ah,", cell.electrical.nominal_voltage, "V")
# 3.0 Ah, 3.2 V
```

A clean import and `SonyLFP()` instantiation confirms that numpy, pandas, scipy, and the packaged CSV lookup data are all wired up. From here, [Getting Started](../getting-started.md) walks through a first simulation in five minutes.
