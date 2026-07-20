# Project Context

## Overview

tg-mcp-spy is a Python MCP (Model Context Protocol) server that caches Telegram channel posts in a local SQLite database and exposes them via MCP tools. It connects to Telegram through a user session (Telethon) and mirrors the user's broadcast-channel subscriptions into a queryable local cache.

## Tech stack

- **Language**: Python 3.12+
- **Package manager**: uv
- **Code style**: ruff + mypy (strict)
- **Testing**: pytest + pytest-asyncio
- **Build backend**: setuptools (via uv)

## Commands

- `make test` — run tests
- `make lint` — run linters
- `make typecheck` — run mypy
- `make format` — format code
- `make check` — run format-check, lint, typecheck, and test

## Domain

- **Channel**: a Telegram broadcast channel the user is subscribed to or has manually added.
- **Tracked channel**: a channel marked for local caching (`is_tracked=True`).
- **Post**: a cached message from a tracked channel, containing Telegram message id, channel reference, UTC timestamp, and text.
- **Sync**: mirroring the user's Telegram dialog list into the local cache (`sync_dialogs`).
- **Update**: fetching new posts for a channel since the last cached message (`update_channel`, `update_all_channels`).

## Architecture

```
src/package_tgmcpspy/
  models.py      — domain dataclasses (Channel, Post, ChannelInfo, MessageInfo),
                   domain exceptions (ConfigError, ChannelNotFoundError, TelegramError),
                   shared identifier normalization (normalize_identifier)
  config.py      — AppConfig dataclass + env-var loading and validation
  db.py          — SQLAlchemy Core table definitions, _SyncRepository,
                   async Repository facade (asyncio.to_thread), init_schema
  telegram.py    — Telethon wrapper (TelegramClientWrapper),
                   FloodWait retry decorator, dialog/message fetching
  server.py      — FastMCP application, lifespan, MCP tools, resources, prompts
```

### Dependency direction

- `models.py` has no internal imports (pure domain).
- `config.py` imports from `models` (ConfigError only).
- `db.py` imports from `models` (dataclasses).
- `telegram.py` imports from `config` and `models`.
- `server.py` imports from `config`, `db`, `models`, and `telegram`.

### Key design decisions

- **SQLAlchemy Core + sync SQLite + `asyncio.to_thread`** (no aiosqlite) — one fewer dependency; simpler typing.
- **Sequential MCP tool processing** — no concurrent Telegram or DB operations; simplifies ordering and rate-limit handling.
- **Immutable cached posts** — edits and deletions on Telegram are ignored; `upsert_posts` only inserts new rows.
- **Per-channel TTL purge** — posts older than a configurable TTL (default 90 days) are purged per-channel at the start of `update_channel`.
- **Domain exceptions raised from tools** — `ConfigError`, `ChannelNotFoundError`, `TelegramError`; FastMCP converts these to MCP error responses. No `{ok, error}` envelopes.
- **No MCP notifications** — pure request/response; no resource subscriptions or events.

## System boundaries

### In scope

- Mirror Telegram broadcast-channel subscriptions into a local cache.
- Fetch and cache channel posts via the Telegram user-session API.
- Expose channel/post operations as MCP tools so clients can list channels, refresh data, and read posts by id or date range.
- Add/remove channels from the local tracked list (does not subscribe/unsubscribe on Telegram).
- Read-only MCP resources for channel lists and single posts.
- Prompt template for channel digests.

### Out of scope

- Subscribing or unsubscribing the user from Telegram channels.
- Fetching private messages, direct messages, or group messages.
- Media download/storage; only post text and metadata are cached.
- Multi-user/multi-tenant support.
- Web UI, CLI commands beyond the existing server entry point, or persistent scheduling.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_ID` | yes | Telegram API id (positive int) |
| `TELEGRAM_API_HASH` | yes | Telegram API hash |
| `TELEGRAM_SESSION_STRING` | yes | Telethon StringSession for user account |
| `TGMCPSPY_DB_PATH` | no | SQLite database path (default: `tgmcpspy.db`) |
| `TGMCPSPY_POST_TTL_DAYS` | no | Post retention in days (default: `90`) |

## Conventions

- Follow PEP 8 and the ruff configuration in `pyproject.toml`.
- Keep functions small and typed.
- Write tests for public APIs and critical paths.
- Store timestamps as UTC ISO-8601 strings in SQLite.
- Never log secrets or post text.
