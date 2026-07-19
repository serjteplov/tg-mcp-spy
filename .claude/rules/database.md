---
paths:
  - "src/**/*.py"
---

# Database Rules

## Query building
- Use an ORM (e.g., SQLAlchemy 2.0) or a query builder; avoid raw SQL strings in application code.
- If raw SQL is unavoidable, use parameterized queries exclusively.

## Migrations
- Use migrations for schema changes; never modify production schema directly.
- Keep migrations backward-compatible when deploying without downtime.

## Performance
- Guard against N+1 queries; use eager loading where appropriate.
- Index foreign keys and commonly queried columns.

## Security
- Never commit connection strings with credentials.
- Load database URLs from environment variables.

## Transactions
- Keep transactions as short as possible.
- Use explicit transaction boundaries; do not rely on auto-commit for multi-step operations.
