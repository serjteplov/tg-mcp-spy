# Final approved implementation plan

> Approved plan for the `channel-post-cache` OpenSpec change.
> Chosen implementation option: **Option A — SQLAlchemy Core + sync SQLite wrapped in `asyncio.to_thread`**.

## Context

The OpenSpec change package `openspec/changes/channel-post-cache/` is approved in principle. The repository is still a minimal FastMCP scaffold (`src/package_tgmcpspy/server.py` has only demo handlers, `tests/test_smoke.py` only tests demos). This document records the concrete execution plan for implementing the Telegram channel/post MCP feature.

## Requirements summary (from OpenSpec)

| Requirement | Source |
|---|---|
| Read `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING` from env (R1–R3) | `specs/channels/spec.md` |
| Use Telethon `StringSession`; fail fast if unauthorized (R2–R3) | `specs/channels/spec.md` |
| SQLite cache via SQLAlchemy, no raw SQL (R11) | `specs/channels/spec.md`, `design.md` |
| Minimal post model: message id, channel, UTC timestamp, text (R12) | `specs/channels/spec.md` |
| Channel identifiers: username or numeric id including `-100...` (R20) | `specs/channels/spec.md` |
| Tools: `list_tracked_channels`, `add_channel`, `remove_channel`, `sync_dialogs`, `update_channel`, `update_all_channels`, `get_post`, `list_channel_posts`, `list_all_posts` (R4–R8, R13–R15) | `specs/channels/spec.md`, `proposal.md` |
| First update fetches last 7 days; later updates fetch newer than cached latest (R9–R10) | `specs/channels/spec.md` |
| All MCP calls processed sequentially (R18) | `specs/channels/spec.md` |
| No MCP notifications or resource subscriptions (R19) | `specs/channels/spec.md` |
| Errors raised as FastMCP exceptions (R24) | `specs/channels/spec.md` |
| `list_channel_posts` / `list_all_posts` return full post text (R21) | `specs/channels/spec.md` |
| `update_all_channels` continues on per-channel failure and reports errors (R22) | `specs/channels/spec.md` |
| Cache public and private broadcast content the same way (R23) | `specs/channels/spec.md` |
| TTL purge posts older than `TGMCPSPY_POST_TTL_DAYS` (default 90) (R25) | `specs/channels/spec.md`, `design.md` |
| Posts immutable; Telegram edits/deletions ignored (R26) | `specs/channels/spec.md` |
| Unit tests only, deterministic, mocked Telethon + in-memory SQLite | `proposal.md`, `design.md` |

## Alignment with OpenSpec documents

This plan implements the approved clarifications from `proposal.md`, `design.md`, and `specs/channels/spec.md`:

- **Data model** (`design.md`) — `channels` and `posts` tables using SQLAlchemy Core, indexes on `(channel_id, timestamp_utc)` and `timestamp_utc`, cascade delete on channel removal.
- **Concurrency** (`design.md`, R18, S15) — FastMCP handlers are async, but all work is done sequentially; no locks or connection pooling beyond a single engine/connection per lifespan.
- **Data retention** (`design.md`, R25, S18) — `Repository.purge_old_posts(ttl_days)` runs at the start of every `update_channel` / `update_all_channels`; default TTL 90 days, configurable via `TGMCPSPY_POST_TTL_DAYS`.
- **Event payloads** (`design.md`, R19, S16) — No notifications; only request/response tools, read-only resources, and one prompt.
- **Private content** (`design.md`, R23, S20) — `TelegramClientWrapper` does not distinguish public/private; it caches whatever the user session can read.
- **Error handling** (`design.md`, R24) — Domain exceptions (`ConfigError`, `ChannelNotFoundError`, `TelegramError`) raised from tools; FastMCP serializes them as standard MCP errors.
- **Full text in lists** (`design.md`, R21, S19) — `list_channel_posts` and `list_all_posts` return the complete `text` field.
- **Partial failures** (`design.md`, R22, S17) — `update_all_channels` iterates sequentially, catches failures per channel, and returns a result object with both successes and errors.
- **Immutability** (R26, S18) — Upsert of posts only inserts new rows; `ON CONFLICT(channel_id, telegram_message_id) DO NOTHING` (or equivalent) means edits/deletions are ignored.

## Chosen implementation option

### Option A: SQLAlchemy Core + sync SQLite wrapped in `asyncio.to_thread`

- Use `sqlalchemy.create_engine("sqlite:///...")` and synchronous `Connection`/`Transaction` operations.
- Introduce a thin async repository facade that calls the sync repository via `asyncio.to_thread(...)`.
- Telegram wrapper stays fully async; DB work is offloaded to threads.

**Why this option was chosen**

- One less dependency (no `aiosqlite`).
- Simpler to type-check with mypy; SQLAlchemy 2.0 Core sync API is mature and well-typed.
- Matches the clarified "all calls sequential" requirement; thread switching is acceptable for low-throughput MCP use.
- Easier to test deterministically (in-memory SQLite in the main thread works naturally).

**Trade-offs**

- Each DB call pays a thread-switch overhead.
- Slightly more code (`async def` wrapper around sync repo).
- Future concurrency would require moving to async DB later.

## Step-by-step implementation plan

### Phase 1 — Tooling and dependencies

1. Edit `pyproject.toml`:
   - Add `telethon>=1.35.0` and `sqlalchemy>=2.0.0` to `[project.dependencies]`.
   - Add `pytest-asyncio>=0.23.0` to `[project.optional-dependencies.dev]`.
   - Add `[tool.pytest.ini_options]` `asyncio_mode = "auto"` and `asyncio_default_fixture_loop_scope = "function"`.
   - Add `[[tool.mypy.overrides]]` `ignore_missing_imports = true` for `telethon.*`.
2. Edit `.pre-commit-config.yaml`: change `pytest-smoke` hook args from `[-q, tests/test_smoke.py]` to run the full suite (e.g., `[-q]` or remove the file argument).
3. Run `uv sync --all-extras` to install dependencies.

### Phase 2 — Domain layer

4. Create `src/package_tgmcpspy/models.py`:
   - `Channel` dataclass.
   - `Post` dataclass.
   - `MessageInfo` / `ChannelInfo` dataclasses for Telegram wrapper returns.
   - Domain exceptions: `ConfigError`, `ChannelNotFoundError`, `TelegramError`.
5. Create `src/package_tgmcpspy/config.py`:
   - `AppConfig` dataclass.
   - `load_config()` reading env vars and validating types/ranges.
   - Default `TGMCPSPY_DB_PATH = Path("tgmcpspy.db")`, `TGMCPSPY_POST_TTL_DAYS = 90`.

### Phase 3 — Database layer

6. Create `src/package_tgmcpspy/db.py`:
   - SQLAlchemy Core `Table` definitions for `channels` and `posts`.
   - Indexes and constraints, including unique `(channel_id, telegram_message_id)` and cascade delete on channel removal (R11, R26).
   - Sync `_SyncRepository` class with methods: `upsert_channel`, `list_tracked_channels`, `add_channel`, `remove_channel`, `get_channel_by_username_or_id`, `upsert_posts`, `get_post`, `list_channel_posts`, `list_all_posts`, `purge_old_posts`.
   - Async `Repository` facade that delegates sync methods via `asyncio.to_thread`.
   - `init_schema(engine)` helper.

### Phase 4 — Telegram adapter

7. Create `src/package_tgmcpspy/telegram.py`:
   - `TelegramClientWrapper` class wrapping `TelegramClient(StringSession(...))`.
   - `connect()` / `disconnect()`.
   - `_with_flood_wait` decorator: retry on `FloodWaitError` up to 3 times, sleep `min(seconds, 60)`.
   - `get_dialogs()` → list of broadcast `ChannelInfo`.
   - `resolve_identifier(identifier)` → `ChannelInfo` (handles username and `-100...` id).
   - `fetch_messages_since(identifier, cutoff)` and `fetch_messages_after(identifier, min_id)` → `list[MessageInfo]`.

### Phase 5 — FastMCP application

8. Rewrite `src/package_tgmcpspy/server.py`:
   - Remove demo `add`, `greeting`, `greet_user` (M1).
   - Define `AppContext` dataclass holding `config`, `repo`, `client`.
   - Add `@asynccontextmanager` lifespan: load config, create engine/repo, connect Telegram client, yield `AppContext`, cleanup on shutdown.
   - Register tools. Each tool raises domain exceptions on failure (R24); `list_channel_posts` and `list_all_posts` return full post text (R21); `update_all_channels` reports per-channel results and errors (R22).
   - Register read-only resources (`channel://list`, `post://{channel}/{post_id}`) and prompt (`channel_digest://{channel}`).
   - No notifications or subscriptions are emitted (R19).
   - Keep `main()` entry point running uvicorn over `mcp`.

### Phase 6 — Tests

9. Delete `tests/test_smoke.py`.
10. Create `tests/conftest.py`:
    - `settings` fixture with in-memory DB and dummy Telegram credentials.
    - `db_engine` / `repo` fixtures using in-memory SQLite.
    - `fake_client` fixture implementing the wrapper interface deterministically.
    - `app_context` and `mcp_context` fixtures for tool tests.
11. Create `tests/test_config.py`:
    - Missing/invalid env vars raise `ConfigError`.
    - Happy path produces expected `AppConfig`.
12. Create `tests/test_db.py`:
    - Schema creation.
    - Channel upsert, tracked flag, add/remove (S2–S4).
    - Post upsert, get, date-range queries with inclusive boundaries (S10).
    - TTL purge behavior (S18).
13. Create `tests/test_telegram.py`:
    - Identifier resolution for username vs numeric id (R20).
    - `fetch_messages_since` / `fetch_messages_after` mapping (R9–R10).
    - FloodWait retry and exhaustion (S14).
14. Create `tests/test_server.py`:
    - `sync_dialogs` upserts dialogs as tracked (S1).
    - `list_tracked_channels` filters correctly (S2).
    - `add_channel` / `remove_channel` only change local flag (S3–S4).
    - `update_channel` initial 7-day backfill vs incremental (S5–S6).
    - `update_all_channels` sequential update and partial failure (S7, S17).
    - `get_post` success and not-found (S8–S9).
    - `list_channel_posts` and `list_all_posts` inclusive date bounds and full text (S10–S11, S19).
    - Sequential handling / no notifications are implicit in the test setup (S15–S16).
    - Private content handled transparently (S20).

### Phase 7 — Verification

15. Run `make check`.
16. Fix any ruff, mypy, or pytest failures.
17. If real Telegram credentials are available, run a manual smoke test:
    ```bash
    export TELEGRAM_API_ID=...
    export TELEGRAM_API_HASH=...
    export TELEGRAM_SESSION_STRING=...
    python -m package_tgmcpspy.server
    ```
    Then exercise `sync_dialogs`, `list_tracked_channels`, `update_all_channels`, `list_all_posts`.

## Exact files to change

### Modified

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `src/package_tgmcpspy/server.py`

### Created

- `src/package_tgmcpspy/config.py`
- `src/package_tgmcpspy/models.py`
- `src/package_tgmcpspy/db.py`
- `src/package_tgmcpspy/telegram.py`

### Deleted

- `tests/test_smoke.py`

## Exact tests to add

- `tests/conftest.py`
- `tests/test_config.py`
- `tests/test_db.py`
- `tests/test_telegram.py`
- `tests/test_server.py`

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Telethon session string must be generated externally. | Fail fast in `connect()` with a clear `ConfigError`. |
| `sync_dialogs` re-tracks channels removed locally. | Document behavior; spec treats this as acceptable. |
| Rate limits slow `update_all_channels`. | Sequential processing + capped FloodWait retries + per-channel partial-failure reporting. |
| TTL purge deletes posts clients expect. | Default 90 days, configurable via env, documented. |
| Private content stored locally. | Env-only session string, no message text in logs, localhost-only server, local DB file. |
| mypy struggles with Telethon types. | `ignore_missing_imports = true` for `telethon.*`; keep untyped surface narrow. |

## Verification

- `make check` must pass before declaring complete.
- Optional manual end-to-end run with real Telegram credentials.
