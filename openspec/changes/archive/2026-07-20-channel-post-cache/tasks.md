# Tasks: Telegram channel post cache for MCP

This file breaks the `channel-post-cache` change into concrete, reviewable tasks. Each task references the relevant requirements (`R#`) and scenarios (`S#`) from `specs/channels/spec.md`.

## Completed tasks

- [x] **T1 — Tooling and dependencies**
  - Add `telethon`, `sqlalchemy` to runtime dependencies and `pytest-asyncio` to dev dependencies.
  - Configure pytest `asyncio_mode = auto`.
  - Update `.pre-commit-config.yaml` smoke hook to run the full test suite.
  - Run `uv sync --all-extras`.
  - Acceptance: `make check` still passes.

- [x] **T2 — Domain models and configuration**
  - Create `src/package_tgmcpspy/models.py` with `Channel`, `Post`, `ChannelInfo`, `MessageInfo`, domain exceptions (`ConfigError`, `ChannelNotFoundError`, `TelegramError`), and `normalize_identifier`.
  - Create `src/package_tgmcpspy/config.py` with `AppConfig` and `load_config()` reading `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`, `TGMCPSPY_DB_PATH`, and `TGMCPSPY_POST_TTL_DAYS`.
  - Acceptance: config validation errors are clear; `make check` passes.

- [x] **T3 — Database layer**
  - Create `src/package_tgmcpspy/db.py` with SQLAlchemy Core tables `channels` and `posts`.
  - `UniqueConstraint("channel_id", "telegram_message_id")` on posts table.
  - Implement `_SyncRepository` + async `Repository` facade via `asyncio.to_thread`.
  - Support channel upserts, tracked list, post upserts (immutable), date-range queries, per-channel TTL purge, cascade delete.
  - Acceptance: `make check` passes.

- [x] **T4 — Telegram client wrapper**
  - Create `src/package_tgmcpspy/telegram.py`.
  - Implement `TelegramClientWrapper` using Telethon `StringSession`.
  - Connect with authorized-session check and fail fast on bad session (R3, S12).
  - Implement `get_dialogs`, `resolve_identifier` using shared `normalize_identifier` (R20), `fetch_messages_since` accepting `ChannelInfo` (R9, S5), and `fetch_messages_after` accepting `ChannelInfo` (R10, S6).
  - Add capped `FloodWaitError` retry (3 retries, max 60 s sleep) (R17, S14).
  - Add mypy override for `telethon.*` in `pyproject.toml`.
  - Acceptance: `make check` passes; wrapper can be mocked deterministically for tests.

- [x] **T5 — MCP server surface**
  - Rewrite `src/package_tgmcpspy/server.py`.
  - Remove demo handlers `add`, `greeting`, `greet_user` (M1).
  - Add FastMCP lifespan with `AppContext` (config, repo, Telegram client).
  - Register tools: `list_tracked_channels`, `add_channel`, `remove_channel`, `sync_dialogs`, `update_channel`, `update_all_channels`, `get_post`, `list_channel_posts`, `list_all_posts` (R4–R8, R13–R15).
  - Tools raise domain exceptions on errors (R24, S9, S13).
  - `update_all_channels` reports per-channel results and continues on failures (R22, S17).
  - `list_channel_posts` / `list_all_posts` return full post text (R21, S19).
  - Register read-only resources `channel://list`, `post://{channel}/{post_id}` and prompt `channel_digest://{channel}`.
  - No notifications or subscriptions are emitted (R19, S16).
  - All calls remain effectively sequential (R18, S15).
  - Acceptance: `make check` passes; server starts when valid env vars are present.

- [x] **T6 — Tests**
  - Delete `tests/test_smoke.py`.
  - Create `tests/conftest.py` with in-memory SQLite engine/repo, fake Telegram client, and app context fixtures.
  - Create `tests/test_config.py` (5 tests: happy path, defaults, missing/invalid env).
  - Create `tests/test_db.py` (7 tests: upsert, tracked filter, set_tracked, duplicate posts, inclusive date range, global TTL purge, per-channel TTL purge).
  - Create `tests/test_telegram.py` (12 tests: normalize_identifier, resolve by username/numeric/-100 prefix/non-channel, fetch_messages_since/after, FloodWait retry and exhaustion).
  - Create `tests/test_server.py` (21 tests: date parsing, resolve by username/numeric/-100/unknown, sync_dialogs, list_tracked_channels, add/remove_channel, update_channel backfill/incremental, update_all_channels success/partial failure, get_post found/not-found, list_channel_posts inclusive range/full text, list_all_posts tracked only).
  - Acceptance: `make check` passes (45 tests total).

- [x] **T7 — Final review and bug fixes**
  - Fixed `normalize_identifier` to correctly strip the `-100` channel/supergroup prefix (R20).
  - Fixed `MCPContext` type alias to provide all 3 generic parameters required by FastMCP's `Context`.
  - Fixed resource decorators to not include `ctx` parameter (FastMCP validates URI params match function params).
  - Removed stale `debug=True` from FastMCP constructor.
  - Updated `openspec/project.md`, `.claude/rules/repository-map.md`, `.claude/rules/error-handling.md`.
  - Updated tasks.md to reflect actual completion status.
  - Acceptance: `make check` passes; 45 tests pass.

## Cross-cutting constraints

- Never commit secrets; credentials come from env vars only.
- Do not modify `.env`.
- Prefer small, focused commits.
- Run `make check` before marking any task complete.
- Keep functions small and explicitly typed.
