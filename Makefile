.PHONY: docs-install docs-serve docs-build docs-clean

docs-install:
	uv sync --group docs

docs-serve:
	uv run mkdocs serve

docs-build:
	# TODO: re-add --strict once all docstrings have type annotations
	uv run mkdocs build

docs-clean:
	uv run mkdocs clean
	rm -rf site/
