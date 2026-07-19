---
paths:
  - "src/**/*.py"
  - "tests/**/*.py"
---

# Change Discipline

## Scope
- Keep the diff minimal. Add only what the task requires.
- Do not refactor unrelated code while implementing a feature.
- Refactor tests in the same change as the code change that requires updating them.

## Verification
- Run `make check` before claiming a task is complete.
- Add or update tests for every behavior change.

## Backward compatibility
- Preserve backward-compatible behavior unless the task explicitly requires breaking changes.
- If a breaking change is needed, document it in the commit message and update dependent tests.

## Autonomy matrix
- **Proceed autonomously**: refactoring, adding tests, adding docstrings, fixing typos.
- **Ask the user before proceeding**: adding dependencies, deleting files, changing CI, changing project structure, renaming public APIs.

## Memory
- Check existing project memory before creating new memory files.
- Prefer updating an existing memory over creating a near-duplicate.
