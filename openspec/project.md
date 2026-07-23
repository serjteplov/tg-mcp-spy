# Project Context

## Overview

tg-mcp-spy is a Python MCP (Model Context Protocol) server that caches messages from Telegram conversations in a local SQLite database and exposes them via MCP tools. It connects through a Telegram user session (Telethon) and mirrors direct messages, legacy group chats, broadcast channels, and supergroups into a queryable local cache.

## Tech stack

- **Language**: Python 3.13+
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

- **Conversation**: a Telegram `Channel`, legacy `Chat`, or `User`, identified by a `kind` discriminator (`channel`, `chat`, or `user`).
- **Tracked conversation**: a conversation marked for local caching (`is_tracked=True`).
- **Post**: a cached message from a tracked conversation, containing Telegram message id, conversation reference, UTC timestamp, and text.
- **Sync**: mirroring every accessible Telegram dialog into the local cache (`sync_dialogs`).
- **Update**: fetching new posts for a conversation since its last cached message (`update_channel`, `update_all_channels`). A first update backfills the previous 7 days for every conversation kind.

Public dataclass and MCP tool names retain the legacy word `channel` for compatibility; in that surface, “channel” means any tracked conversation.

## Architecture

```
src/package_tgmcpspy/
  models.py      — domain dataclasses (Channel, Post, ChannelInfo, MessageInfo),
                   ConversationKind discriminator, domain exceptions,
                   shared identifier normalization (normalize_identifier)
  config.py      — AppConfig dataclass + env-var loading and validation
  db.py          — SQLAlchemy Core table definitions, schema compatibility,
                   _SyncRepository, async Repository facade (asyncio.to_thread)
  telegram.py    — Telethon wrapper (TelegramClientWrapper), entity-kind dispatch,
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

- **Discriminated conversation model** — `Channel` and `ChannelInfo` carry `kind=channel|chat|user`; class and MCP tool names remain unchanged to preserve compatibility.
- **Backward-compatible SQLite schema** — the dedicated `kind` column defaults existing rows to `channel`, avoiding a manual migration.
- **SQLAlchemy Core + sync SQLite + `asyncio.to_thread`** (no aiosqlite) — one fewer dependency; simpler typing.
- **Sequential MCP tool processing** — no concurrent Telegram or DB operations; simplifies ordering and rate-limit handling.
- **Immutable cached posts** — edits and deletions on Telegram are ignored; `upsert_posts` only inserts new rows.
- **Per-conversation TTL purge** — posts older than a configurable TTL (default 90 days) are purged for each conversation at the start of `update_channel`.
- **Domain exceptions raised from tools** — `ConfigError`, `ChannelNotFoundError`, `TelegramError`; FastMCP converts these to MCP error responses. No `{ok, error}` envelopes.
- **No MCP notifications** — pure request/response; no resource subscriptions or events.

## System boundaries

### In scope

- Mirror all accessible Telegram dialogs into a local cache, including direct messages, legacy group chats, broadcast channels, and supergroups.
- Fetch and cache text messages through the Telegram user-session API.
- Expose conversation/post operations as MCP tools so clients can list tracked conversations, refresh data, and read posts by id or date range.
- Add/remove conversations from the local tracked list without changing Telegram membership or subscriptions.
- Read-only MCP resources for conversation lists and single posts.
- Prompt template for conversation digests.

### Out of scope

- Joining, leaving, subscribing to, or unsubscribing from Telegram conversations.
- Group membership management, contact management, or megagroup migration logic.
- Media download/storage; only message text and metadata are cached.
- Multi-user/multi-tenant support.
- Web UI, CLI commands beyond the existing server entry point, or persistent scheduling.

## Privacy and security

- Telegram credentials and the session string come from environment variables and are never logged.
- Message text, including private DM and group content, is not written to logs.
- The server binds locally by default.
- The SQLite database may contain private conversation history; host filesystem access and backups must be protected accordingly.

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
