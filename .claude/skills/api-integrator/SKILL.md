---
name: api-integrator
description: Integrate an external API into the project. Use with --type (rest, graphql, grpc, websocket, etc.).
allowed-tools:
  - Read
  - Bash
  - Edit
  - Write
---

# API Integrator

## Trigger
Adding a new external API client or integration.

## Procedure
1. Check `pyproject.toml` for existing HTTP clients.
2. Pick a library based on `--type`:
   - `rest` → `httpx` or `requests`
   - `graphql` → `gql`
   - `grpc` → `grpcio`
3. Add the dependency to `pyproject.toml` if new.
4. Draft a typed client module under `src/package_snowball/`.
5. Add error handling and timeouts.
6. Write tests with mocked responses.
7. Run `make check`.

## Output
- Proposed module path.
- Dependency list if any.
- Test plan.
