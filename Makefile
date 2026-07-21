PYTHON := .venv/bin/python
PYTEST := .venv/bin/pytest
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
PRE_COMMIT := .venv/bin/pre-commit

.PHONY: help setup install-dev format format-check lint typecheck test check clean pre-commit-install

help:
	@echo "setup               Create venv, install dev deps, and install pre-commit hooks"
	@echo "install-dev         Install project in editable mode with dev extras"
	@echo "format              Run ruff formatter"
	@echo "format-check        Check formatting without modifying files"
	@echo "lint                Run ruff linter"
	@echo "typecheck           Run mypy"
	@echo "test                Run pytest"
	@echo "check               Run format-check, lint, typecheck, and test"
	@echo "pre-commit-install  Install git hooks"
	@echo "clean               Remove caches"

setup:
	uv sync --all-extras
	$(PRE_COMMIT) install

install-dev:
	uv sync --all-extras

format:
	$(RUFF) format src tests

format-check:
	$(RUFF) format --check src tests

lint:
	$(RUFF) check src tests

typecheck:
	$(MYPY) src tests

test:
	$(PYTEST)

test-one:
	uv run pytest $(TEST) -q --tb=short

check: format-check lint typecheck test

pre-commit-install:
	$(PRE_COMMIT) install

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
