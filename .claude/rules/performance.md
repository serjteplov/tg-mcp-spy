---
paths:
  - "src/**/*.py"
---

# Performance Guidelines

## General
- Do not optimize without profiling or a clear performance requirement.
- Keep code readable first.

## I/O and loops
- Be conscious of big-O for loops over large inputs.
- Batch I/O operations when possible.

## Caching
- Use `functools.lru_cache` for pure functions with expensive computation and stable arguments.
- Avoid caching functions with mutable arguments or side effects.

## Generators
- Prefer generators (`yield`) over building large lists when the full collection is not needed.
- Use `yield from` for delegating to sub-generators.

## Anti-patterns
- No sleep/busy-waiting loops for synchronization.
- Do not load large files entirely into memory if streaming is possible.
- Avoid repeated attribute lookups inside tight loops; cache locally if needed.

## Example
```python
# Prefer
for line in pathlib.Path("large.txt").open():
    process(line)

# Avoid
lines = pathlib.Path("large.txt").read_text().splitlines()
for line in lines:
    process(line)
```
