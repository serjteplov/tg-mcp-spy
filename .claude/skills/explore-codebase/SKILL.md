---
name: explore-codebase
description: Search and map the codebase before making changes. Read-only exploration.
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
---

# Explore Codebase

## Trigger
Mapping code, tracing dependencies, or assessing change impact.

## Procedure
1. Grep for the target symbol or module in `src/` and `tests/`.
2. Trace imports and call graphs.
3. List directly and indirectly affected files.
4. Check for existing patterns to reuse.

## OpenSpec Cross-Reference
When exploring code related to a domain, cross-check findings against
`openspec/specs/<domain>/spec.md` to detect drift between documented
and actual behavior. Report any mismatch found.

## Output
- Affected files list.
- Key findings (3–6 bullets).
- Reusable patterns found.
- Open questions.
