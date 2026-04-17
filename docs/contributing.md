# Contributing

Contributions of all sizes are welcome — bug fixes, new cell or converter models, and documentation improvements.

## Development setup

Clone and install everything in one go:

```bash
git clone https://github.com/tum-ees/simses.git
cd simses
uv sync --all-groups
```

This installs runtime dependencies plus the `dev` and `docs` groups (and pulls `notebooks` transitively via `docs`). See [Installation](guides/installation.md) for per-group setups.

## Running tests

```bash
uv run pytest
```

All tests should pass on a clean checkout. The suite runs in under 10 seconds on a modern machine.

Some subsystems use parameterised spec registries (`CellModelSpec`, `ConverterModelSpec`, `CalendarModelSpec`, `CyclicModelSpec`) so that adding a new shipped model automatically pulls in the generic test coverage. See the extension guides for the per-subsystem pattern.

## Linting and formatting

```bash
uv run ruff check .
uv run ruff format .
```

CI enforces both. Run them locally before opening a PR — the `ruff check` output tells you exactly what to fix, and `ruff format` is idempotent. Spelling is checked with `codespell` on the same CI step.

## Building the docs

```bash
uv run mkdocs serve -w src/simses
```

Starts a live-reloading preview at <http://127.0.0.1:8000>. The `-w src/simses` flag extends the watcher to the source tree so docstring edits trigger a rebuild (the default only watches `docs/`).

To reproduce the CI build locally:

```bash
uv run mkdocs build --strict
```

`--strict` fails on any warning — broken cross-references, missing nav entries, etc. Always the last gate before shipping a docs change.

## Style conventions

- **Code style**: `ruff format` handles formatting; `ruff check` enforces lint rules. The rule selection is in `pyproject.toml`.
- **Docstrings**: Google style, as configured in `mkdocs.yml`. Constructor `Args:` live on `__init__`, not the class docstring.
- **State is data, logic is code**: all mutable state goes in plain `@dataclass` objects; methods live on the companion class. See [CLAUDE.md](https://github.com/tum-ees/simses/blob/main/CLAUDE.md) for the project-level design principles.
- **Protocols at extension points**: new behaviour that varies between implementations (loss models, aging laws, HVAC, etc.) goes through a `typing.Protocol`, not subclassing.

## Pull request process

1. Open an issue first for anything non-trivial — it's cheaper than rewriting a PR.
2. Fork + branch from `main`. Keep the branch focused on one change.
3. Run tests, ruff, and a strict docs build locally before pushing.
4. Open a PR with a short summary of *why* the change is needed (not just *what*).
5. CI will re-run tests, lint, and strict docs. Fix any failures before requesting review.

## Reporting issues

Bug reports and feature requests go on the [GitHub issue tracker](https://github.com/tum-ees/simses/issues). For bugs, include:

- Python version (`python --version`).
- simses version (`git rev-parse HEAD` for a source install).
- A minimal reproducing example — the smaller the snippet, the faster the fix.

## Licensing

By contributing you agree that your contributions will be released under the same [BSD 3-Clause License](https://github.com/tum-ees/simses/blob/main/LICENSE) as the rest of the project.
