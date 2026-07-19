---
paths:
  - "**/*"
---

# Repository Map

## Layout
- `src/package_snowball/` — application code
- `tests/` — pytest suite
- `docs/` — specs, ADRs, and notes
- `docs/adr/` — architecture decision records

## Module hierarchy
- `src/package_snowball/core/` — domain logic, models, business rules
- `src/package_snowball/adapters/` — external integrations (API clients, DB, files)
- `src/package_snowball/entrypoints/` — CLI, HTTP handlers, scheduled jobs
- `src/package_snowball/config/` — settings, environment parsing

## Dependency direction
- Domain modules (`core/`) must not import from adapters or entrypoints.
- Adapters may import from domain.
- Entrypoints may import from domain and adapters.

## Entry points
- `Makefile` — development commands (`make check`, `make test`, etc.)
- `pyproject.toml` — project metadata and tool configuration

## Where to add code
- New modules → `src/package_snowball/`
- New tests → `tests/`
- New decisions → `docs/adr/`
- New CLI commands → `src/package_snowball/entrypoints/cli.py` or a new module under `entrypoints/`
- New config schemas → `src/package_snowball/config/`
