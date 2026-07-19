---
paths:
  - "src/**/*.py"
---

# Error-Handling Patterns

## Custom exceptions
- Define domain exceptions in `package_snowball.exceptions`.
- Inherit from a base `SnowballError` for catchability.

## Wrapping
- Wrap low-level errors at module boundaries with context.
- Use `raise CustomError("...") from e` to preserve tracebacks.

## Anti-patterns
- No bare `except:` or `except Exception:` without explicit re-raise.

## Retries
- Keep retry logic at I/O boundaries, not business logic.
- Always cap retries and use backoff.

## Logging exceptions
- Log exceptions at the boundary where they are handled, not at every layer.
- Use `logger.exception("message")` inside `except` blocks to capture the traceback automatically.

## User-facing vs internal errors
- User-facing errors should have clear, actionable messages.
- Internal errors should include debugging context (variable values, request IDs) but never expose sensitive data.
