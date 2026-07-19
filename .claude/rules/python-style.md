---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---

# Python Style Rules

## General
- Follow the existing project structure and naming.
- Prefer readable code over compact code.
- Avoid premature abstraction.
- Keep functions focused and short. Aim for ≤30 lines; >50 lines should trigger refactoring consideration.

## Imports
- Use absolute imports from `package_snowball`.
- Keep imports grouped and sorted.
- Remove unused imports.

## String formatting
- Prefer f-strings for simple interpolation.
- Use `.format()` or templates for complex patterns with many substitutions.

## Docstrings
- Use Google-style docstrings for public functions, classes, and modules.
- One-line docstrings are acceptable for trivial cases; use multi-line for non-trivial logic.

## Modern Python (3.13)
- Use the walrus operator `:=` sparingly — only when it clearly reduces duplication.
- Prefer structural pattern matching (`match`/`case`) over deep `if/elif` chains when unpacking variants.

## Error handling
- Raise specific exceptions.
- Do not swallow exceptions silently.
- Include useful error messages.

## Logging
- Do not use `print()` for application behavior.
- If logging is needed, use the standard `logging` module.

## Changes
- Avoid unrelated refactors in the same change.
- Preserve backward-compatible behavior unless the task requires otherwise.
