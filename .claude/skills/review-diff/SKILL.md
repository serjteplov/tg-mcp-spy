---
name: review-diff
description: Use when reviewing local changes before commit, especially for Python code, tests, and project configuration.
allowed-tools:
  - Read
  - Bash
  - Grep
---

# Review Diff

## Trigger
Reviewing local changes before commit or after a coding slice.

## Procedure
1. Inspect `git diff --stat` and `git diff -- src tests`.
2. Check for accidental secrets, debug code, commented dead code, and noisy changes.
3. Verify naming, typing, and test impact.
4. Confirm formatting with `make lint`.
5. Flag missing tests for changed behavior.
6. Suggest the smallest follow-up fixes first.

## Focus areas
- Public function signatures.
- Error handling.
- Type hints.
- Test coverage for new logic.
- Unintended config churn.
- Avoid duplicating logic in tests; prefer shared fixtures or helpers.

## OpenSpec Scenario Check
If the diff is tied to an active `openspec/changes/<feature-name>/`,
verify each Given/When/Then scenario in its delta spec is satisfied by
the code. List any unmet scenario as a blocking review comment.

## Output
Return:
- critical issues,
- medium issues,
- nice-to-have improvements,
- ready-to-commit verdict.
