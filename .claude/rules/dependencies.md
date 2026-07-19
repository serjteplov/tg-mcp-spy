---
paths:
  - "pyproject.toml"
  - "src/**/*.py"
---

# Dependency Rules

## Adding dependencies
- Ask before adding new dependencies.
- Prefer the standard library unless a third-party package is clearly justified.
- Keep the dependency tree shallow and well-maintained.

## Where to add
- Add runtime dependencies to `[project.dependencies]` in `pyproject.toml`.
- Add development dependencies to `[project.optional-dependencies.dev]`.

## Version pinning
- Pin minimum versions, not exact versions, for libraries.
- Example: `httpx>=0.27`, not `httpx==0.27.0`.

## After adding
- Run `make check` after adding dependencies to ensure resolution is clean.
- Do not commit lock files unless the project explicitly uses a lock-file workflow.

## Removing dependencies
- Remove unused dependencies promptly to keep the environment lean.
- Check for transitive usage before removing.
