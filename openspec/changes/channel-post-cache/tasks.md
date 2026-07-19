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
  - Create `src/package_tgmcpspy/models.py` with `Channel`, `Post`, `ChannelInfo`, `MessageInfo`, and domain exceptions (`ConfigError`, `ChannelNotFoundError`, `TelegramError`).
  - Create `src/package_tgmcpspy/config.py` with `AppConfig` and `load_config()` reading `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`, `TGMCPSPY_DB_PATH`, and `TGMCPSPY_POST_TTL_DAYS`.
  - Acceptance: config validation errors are clear; `make check` passes.

- [x] **T3 — Database layer**
  - Create `src/package_tgmcpspy/db.py` with SQLAlchemy Core tables `channels` and `posts`.
  - Implement `_SyncRepository` + async `Repository` facade via `asyncio.to_thread`.
  - Support channel upserts, tracked list, post upserts (immutable), date-range queries, TTL purge, cascade delete.
  - Acceptance: `make check` passes.

## Remaining tasks

- [ ] **T4 — Telegram client wrapper**
  - Create `src/package_tgmcpspy/telegram.py`.
  - Implement `TelegramClientWrapper` using Telethon `StringSession`.
  - Connect with authorized-session check and fail fast on bad session (R3, S12).
  - Implement `get_dialogs`, `resolve_identifier` (username / `-100...` id) (R20), `fetch_messages_since` (last 7 days) (R9, S5), and `fetch_messages_after` (newer than cached latest) (R10, S6).
  - Add capped `FloodWaitError` retry (3 retries, max 60 s sleep) (R17, S14).
  - Add mypy override for `telethon.*` in `pyproject.toml`.
  - Acceptance: `make check` passes; wrapper can be mocked deterministically for tests.

- [ ] **T5 — MCP server surface**
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

- [ ] **T6 — Tests**
  - Delete `tests/test_smoke.py`.
  - Create `tests/conftest.py` with in-memory SQLite engine/repo, fake Telegram client, and mock MCP context fixtures.
  - Create `tests/test_config.py` for validation and happy path.
  - Create `tests/test_db.py` covering schema, channel/post CRUD, inclusive date ranges (S10), and TTL purge (S18).
  - Create `tests/test_telegram.py` covering identifier resolution (R20), fetch strategies (R9–R10), and FloodWait retry (S14).
  - Create `tests/test_server.py` covering all tools and scenarios S1–S11, S15–S20.
  - Acceptance: `make check` passes; coverage for changed code is ≥80%.

- [ ] **T7 — Final review and archive**
  - Review diff for correctness, security, typing, and test coverage.
  - Update `docs/adr/` if any significant architectural decision changed during implementation.
  - Archive the change: merge delta spec into `openspec/specs/` via the doc-writer stage.
  - Acceptance: `make check` passes; OpenSpec docs are consistent with the code.

## Cross-cutting constraints

- Never commit secrets; credentials come from env vars only.
- Do not modify `.env`.
- Prefer small, focused commits.
- Run `make check` before marking any task complete.
- Keep functions small and explicitly typed.
- Follow the package name `package_tgmcpspy` (not the stale `package_snowball` references in some template rules).
