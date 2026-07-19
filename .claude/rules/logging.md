---
paths:
  - "src/**/*.py"
---

# Logging Rules

## General
- Use the standard `logging` module; do not use `print()` for application behavior.
- Create module-level loggers: `logger = logging.getLogger(__name__)`.

## Log levels
- `DEBUG` — development detail, verbose tracing.
- `INFO` — business events and milestones.
- `WARNING` — recoverable issues or unexpected but handled conditions.
- `ERROR` — failures requiring attention.

## Structured logging
- Use `logging.info("msg", extra={"key": value})` for machine-parseable events.
- Prefer structured fields over embedding values in message strings when logs are consumed by aggregators.

## Context and tracing
- Include correlation IDs in log context for traced operations.
- Pass context through `extra` or logging adapters rather than mutating global state.

## Security
- Never log secrets, tokens, passwords, or PII at `INFO` or below.
- If sensitive data must be logged for debugging, log it at `DEBUG` and ensure debug logs are not persisted in production.

## Exceptions
- Use `logger.exception("message")` inside `except` blocks to capture tracebacks automatically.
- Do not log and re-raise the same exception at every layer; log at the handling boundary.
