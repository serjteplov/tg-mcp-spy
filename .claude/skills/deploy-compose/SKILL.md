---
name: deploy-compose
description: Build, run, and manage local Docker Compose deployments. Use for containerized dev environments, service orchestration, and deployment health checks. Accepts action and optional flags via args.
allowed-tools:
  - Read
  - Bash
  - Edit
---

# Deploy Compose

## Trigger
- Building or running the project with Docker Compose.
- Starting dependent services (database, cache, broker) for local development or tests.
- Checking deployment health, logs, or restarting containers.

## Arguments
Accept `args` as a space-separated string. Parse it before executing.

Supported actions (first positional argument):
- `up` — start services (`-d` implied)
- `down` — stop services
- `build` — build images
- `logs` — tail logs
- `ps` — list containers and health
- `exec` — run a one-off command inside a service container
- `restart` — restart services

Optional flags:
- `--service <name>` — target specific service(s); can be repeated
- `--file <path>` — override compose file discovery
- `--no-detach` — for `up` only, run in foreground

Defaults when args are omitted:
- Action defaults to `up` if the intent is to start/deploy.
- If no `--file` is given, fall back to the discovery in Procedure step 1.

Examples:
- `up --service db`
- `down`
- `logs --service app`
- `up --file docker-compose.test.yml --service app --service db`
- `exec --service app -- python manage.py migrate`
- `ps`

## Procedure
1. Parse `args` to determine action and flags (`--service`, `--file`, `--no-detach`).
2. Inspect the repo for compose files **only if `--file` is not provided**:
   - `docker-compose.yml`, `docker-compose.yaml`
   - `compose.yml`, `compose.yaml`
   - Files under `docker/`, `deploy/`, or `infra/`
3. Check for a `Makefile` or scripts with compose targets; prefer them only if they match the requested action exactly.
4. Build the command:
   - If `--file` is given, prepend `-f <path>`.
   - Append the action (`up`, `down`, `build`, `logs`, `ps`, `exec`, `restart`).
   - Append service names if `--service` flags are present.
   - Append action-specific defaults (e.g., `-d` for `up` unless `--no-detach`).
5. Execute the composed command.
6. If migrations or one-off commands are needed, run them inside the relevant container or use project-specific scripts.
7. Verify the deployment by checking running containers and exposed ports.

## Safety rules
- Never use `docker compose down -v` unless explicitly asked — it destroys named volumes and data.
- Do not commit secrets or `.env` files with real credentials.
- Prefer `docker compose` (v2) over `docker-compose` (v1) when available.

## Output
- Commands executed.
- Service status and health summary.
- Any issues encountered (port conflicts, failing containers, missing images).
- Next steps if the deployment needs further configuration.
