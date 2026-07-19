# Project Context

Global context for the Cashback project. Keep this file concise and up to date.

## Overview

Cashback is a Python CLI application that recommends which cashback categories to select on debit cards across multiple banks in order to maximize a weighted total cashback score.

## Tech stack

- **Language**: Python 3.13+
- **Package manager**: pip (venv-based; Makefile uses `.venv/bin/pip`)
- **Code style**: ruff + mypy
- **Testing**: pytest + hypothesis
- **Build backend**: setuptools

## Commands

- `make test` — run tests
- `make lint` — run linters
- `make typecheck` — run mypy
- `make format` — format code
- `make check` — run format-check, lint, typecheck, and test

## Domain

- **Bank**: a financial institution where the user holds a debit card.
- **Category**: a spending category (e.g., groceries, fuel) with a Russian name, English alias, description, and weight.
- **Offering**: a cashback percentage offered by a specific bank for a specific category.
- **User config**: the user’s banks, each with its category limit and offerings.
- **Optimization result**: the recommended category selection per bank, total weighted score, and any unassigned categories.
- **History**: persisted record of past optimization runs.

## Architecture

- `src/package_cashback/` — application package.
  - `models.py` — domain dataclasses.
  - `config.py` — config loading and validation.
  - `optimizer.py` — branch-and-bound solver.
  - `formatters.py` — table and JSON output.
  - `history.py` — history persistence.
  - `wizard.py` — interactive config wizard.
  - `__main__.py` — CLI entry point.
- `tests/` — pytest suite.
- `openspec/` — product specs and implementation plans.

## System boundaries

### In scope

- Recommend which cashback categories to select on the user’s debit cards.
- Support multiple banks, each with its own category limit and offerings.
- Optimize a weighted total cashback score based on user-supplied category weights.
- Load user configuration from local JSON files and validate it.
- Persist optimization history to a local append-only JSON file.
- Provide a CLI with human-readable table output and machine-readable JSON report.
- Offer an interactive wizard for building or editing a user config.

### Out of scope

- Credit cards, credit limits, or lending products.
- Real-time bank integrations, account balances, or transaction feeds.
- Actual payment processing, money transfers, or card management.
- Authentication, authorization, or multi-user accounts.
- Cloud sync, remote storage, or hosted services.
- Mobile, web, or desktop GUI.
- Tracking actual spending or providing budgeting advice.
- Support for currencies other than Russian rubles (RUB).

## Decisions

- Solver: custom branch-and-bound (stdlib only) instead of an external ILP or graph library.
- Output: human-readable table plus JSON report.
- Persistence: append-only local JSON history file.

## Conventions

- Follow PEP 8 and the ruff configuration in `pyproject.toml`.
- Keep functions small and typed.
- Write tests for public APIs and critical paths.
- Use `decimal.Decimal` for percentages and scores.
