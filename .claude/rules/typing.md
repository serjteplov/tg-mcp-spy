---
paths:
  - "src/**/*.py"
---

# Typing Rules

## Expectations
- Add type hints to all new or modified functions.
- Add explicit return types for non-trivial functions.
- Prefer concrete types over `Any`.

## When to allow Any
- Only at boundaries where typing is impractical.
- Keep the unsafe area narrow and documented.

## Data structures
- Prefer `TypedDict`, `dataclass`, or small classes for structured data.
- Avoid passing around large untyped dictionaries without need.

## Protocols and ABCs
- Use `Protocol` for structural subtyping (duck typing with types).
- Use `ABC` for nominal inheritance with shared implementation.

## Generics and forward references
- Use `TypeVar` and generics when a function or class must work with multiple types safely.
- Use `from __future__ import annotations` to avoid forward-reference string quotes in Python 3.13.

## Cast
- Avoid `cast()` when possible; prefer runtime checks or narrowing.
- If `cast()` is required, keep it narrow and explain why in a comment.

## Mypy
- Keep the codebase mypy-clean for changed files.
- If a type ignore is required, keep it narrow and explain why.
