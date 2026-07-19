---
name: refactor-small-safe
description: Clean up code without changing behavior. Stepwise and verified.
allowed-tools:
  - Read
  - Bash
  - Edit
  - MultiEdit
---

# Refactor Small and Safe

## Trigger
Cleaning code, removing duplication, or improving readability.

## Procedure
1. Identify the smallest scope for the refactor.
2. Run `make test` to establish baseline.
3. Apply the minimal change.
4. Run `make test` again to verify behavior.
5. Run `make check` for style.

## Output
- Changed files.
- Before/after test results.
- Risk note if any behavior edge cases exist.
