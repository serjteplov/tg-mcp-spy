---
paths:
  - "tests/**/*.py"
  - "src/**/*.py"
---

# Testing Rules

## Principles
- Every behavior change should have a test or a clear reason why not.
- Prefer fast deterministic unit tests.
- One test should validate one behavior focus.

## Test naming
- Name tests as `test_<unit>_<condition>_<expected>`.
- Example: `test_calculate_discount_negative_price_raises_value_error`.

## Test style
- Use `pytest`.
- Arrange data explicitly inside the test.
- Use `@pytest.mark.parametrize` instead of loops in tests.

## Fixtures
- Shared fixtures go in `tests/conftest.py`.
- Prefer `function` scope unless broader scope is clearly justified.
- Avoid over-mocking when simple real objects are enough.

## Scope
- Test public behavior first.
- Do not add flaky time- or network-dependent tests.

## Coverage
- Maintain ≥80% coverage for `src/`.

## Minimum check
For changed Python code, run:
```bash
make test
```
