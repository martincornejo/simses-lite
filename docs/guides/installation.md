# Installation

## Requirements

- Python 3.12 or higher

## Install from PyPI

```bash
pip install simses
```

## Install with uv

[uv](https://docs.astral.sh/uv/) is the recommended tool for managing Python environments.

```bash
uv add simses
```

## Development Install

To install from source for development:

```bash
git clone https://github.com/tum-ees/simses.git
cd simses
uv sync --group dev
```

## Running Tutorials Locally

To run the demo notebook locally:

```bash
uv sync --group notebooks
uv run jupyter notebook notebooks/demo.ipynb
```

## Verify Installation

```python
import simses
print(simses.__version__)
```

[PLACEHOLDER: Add expected output]
