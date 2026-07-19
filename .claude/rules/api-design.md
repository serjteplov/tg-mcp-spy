---
paths:
  - "src/**/*.py"
---

# API Design Rules

## Public surface
- Keep the public API narrow. Export intended names via `__all__`.
- Prefer modules over flat namespaces.

## Interfaces
- Use explicit arguments. Avoid `**kwargs` in public functions.
- Return concrete types; avoid large untyped dictionaries.

## Stability
- Preserve backward-compatible behavior unless asked otherwise.
- Ask before renaming or removing public symbols.

## Module naming
- Public modules should have clear, descriptive names.
- Internal implementation details should live in private modules or subpackages (prefixed with `_`).

## Async APIs
- If providing both sync and async variants, name the async version with an `a_` prefix or an `Async` suffix consistently.
- Prefer `async`/`await` for I/O-bound operations; use threads or processes for CPU-bound work.
