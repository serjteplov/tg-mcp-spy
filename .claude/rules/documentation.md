---
paths:
  - "**/*.md"
  - "src/**/*.py"
---

# Documentation Rules

## Docstrings
- Use Google-style docstrings for public functions, classes, and modules.
- One-line docstrings are acceptable for trivial cases; use multi-line for non-trivial logic.
- Document args, returns, and raises for public APIs.

## Module docstrings
- Every public module should start with a short docstring explaining its purpose.
- Keep it concise — elaborate details belong in README or ADRs.

## README updates
- When adding a new CLI command or public API, update `README.md` with a usage example.
- When changing setup or installation steps, update `README.md` immediately.

## Architecture decisions
- Record significant architectural decisions in `docs/adr/` using the existing numbering convention.
- ADRs should be concise: Context, Decision, Consequences.

## Code comments
- Prefer clear code over comments that explain what the code does.
- Use comments to explain *why* a non-obvious choice was made.
- Keep comments up to date; outdated comments are worse than no comments.
