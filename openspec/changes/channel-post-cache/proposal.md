# Proposal: Telegram channel post cache for MCP

## Problem

The `tg-mcp-spy` MCP server is currently a demo scaffold. It exposes placeholder `add`, `greeting`, and `greet_user` handlers and has no integration with Telegram. Users cannot query their subscribed channels or retrieve posts through the MCP protocol.

## Goal

Turn the server into a production-ready MCP tool that:

- Mirrors the user's Telegram channel subscriptions.
- Maintains a local, queryable cache of channel posts.
- Exposes channel/post operations as MCP tools so clients can list channels, refresh data, and read posts by id or date range.

## Scope

### In scope

- User-session Telegram integration via Telethon.
- Environment-based credential loading (`TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`).
- SQLite-backed cache of channels and posts.
- MCP tools:
  - `list_tracked_channels`
  - `add_channel`
  - `remove_channel`
  - `sync_dialogs`
  - `update_channel`
  - `update_all_channels`
  - `get_post`
  - `list_channel_posts`
  - `list_all_posts`
- Read-only MCP resources for channels and single posts.
- A prompt template for channel digests.
- Unit tests with mocked Telethon and in-memory SQLite.

### Out of scope

- Subscribing or unsubscribing the user from Telegram channels (add/remove affect only the local cache).
- Fetching private messages, direct messages, or groups.
- Media download/storage; only post text and metadata are cached.
- Web scraping of `https://t.me/s/...`; all data comes through the Telegram API.
- Multi-user/multi-tenant support.
- Web UI, CLI commands beyond the existing server entry point, or persistent scheduling.

## Acceptance criteria

1. `make check` passes after the change.
2. All new MCP tools are covered by deterministic unit tests.
3. The server starts and exposes the documented tools when credentials are supplied.
4. Secrets are never committed or logged.
5. OpenSpec delta-spec and design documents are approved and archived.

## Risks

- Telethon user session string must be generated externally; bad or missing credentials fail on startup.
- Telegram rate limits (`FloodWaitError`) may slow large updates; `update_all_channels` reports per-channel partial failures.
- `sync_dialogs` will re-track channels that were previously removed locally because it mirrors Telegram state.
- A configurable TTL purge may delete cached posts that clients later expect to exist.
- Private-channel content is cached locally alongside public content; the local database and session string must be protected by the host.
- All MCP calls are processed sequentially, which keeps the implementation simple but may be slow with many channels.

## Data retention and security

- Posts older than a configurable TTL (default 90 days) may be purged automatically.
- The session string is read from environment variables only and never logged or committed.
- Message text is not written to logs.
- The server binds to `127.0.0.1` by default and keeps the cache in a local SQLite file.

## Dependencies

- `telethon` — Telegram user-session client.
- `sqlalchemy` — typed SQLite access without raw SQL.
- `pytest-asyncio` — async test support.

## Estimated effort

Small-to-medium: roughly one implementation slice plus test/review cycle.
