---
paths:
  - "**/*"
---

# Repository Map

## Layout
- `src/<package>/` — application code
- `tests/` — pytest suite
- `docs/` — notes and documentation
- `openspec/adr/` — architecture decision records
- `openspec/` — product specs and implementation plans
  - `openspec/specs/` — current system behavior (single source of truth)
  - `openspec/changes/` — in-progress and archived feature proposals

## Module hierarchy
- `models.py` — domain dataclasses, exceptions, shared utilities
- `config.py` — settings, environment parsing
- `db.py` — database tables, repository, schema initialization
- `telegram.py` — external integrations (API clients, wrappers)
- `server.py` — entry point, HTTP/MCP handlers, lifespan

## Dependency direction
- Domain modules (`models`) must not import from adapters or entrypoints.
- Adapters (`db`, `telegram`) may import from domain.
- Entrypoints (`server`) may import from domain and adapters.

## Entry points
- `Makefile` — development commands (`make check`, `make test`, etc.)
- `pyproject.toml` — project metadata and tool configuration

## Where to add code
- New modules → `src/<package>/`
- New tests → `tests/`
- New decisions → `openspec/adr/`
- New specs → `openspec/specs/` (only via delta-spec merge)
- New change proposals → `openspec/changes/`
