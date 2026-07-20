# Design: Telegram channel post cache for MCP

## Overview

Replace the demo FastMCP handlers with a real Telegram user-session spy that caches channel posts in SQLite and exposes the required operations as MCP tools.

## Module layout

```
src/package_tgmcpspy/
  __init__.py
  config.py            # AppConfig dataclass + env loading/validation
  models.py            # Channel, Post, MessageInfo dataclasses
  db.py                # SQLAlchemy Core tables + async repository
  telegram.py          # Telethon wrapper, dialogs, messages, retries
  server.py            # FastMCP app, lifespan, tools, resources, prompts, main()

tests/
  conftest.py          # in-memory DB fixture, fake Telegram wrapper, mock context
  test_config.py
  test_db.py
  test_telegram.py
  test_server.py
```

## Configuration

Env vars loaded in `config.py`:

| Variable | Required | Type / default |
|---|---|---|
| `TELEGRAM_API_ID` | yes | positive int |
| `TELEGRAM_API_HASH` | yes | non-empty str |
| `TELEGRAM_SESSION_STRING` | yes | non-empty str |
| `TGMCPSPY_DB_PATH` | no | `Path("tgmcpspy.db")` |
| `TGMCPSPY_POST_TTL_DAYS` | no | `90` |

Validation fails fast with a clear error message. No secrets are read from files or CLI args.

## Data model

SQLite tables defined with SQLAlchemy Core:

### `channels`

- `id` — integer primary key.
- `telegram_id` — integer, unique, the Telegram channel id.
- `username` — text, nullable.
- `title` — text, non-empty default `''`.
- `is_tracked` — boolean, default `False`.
- `last_message_id` — integer, nullable; newest cached Telegram message id.
- `last_fetched_at` — UTC ISO-8601 text, nullable.

### `posts`

- `id` — integer primary key.
- `channel_id` — foreign key to `channels.id`, cascade delete.
- `telegram_message_id` — integer.
- `text` — text, default `''`.
- `timestamp_utc` — UTC ISO-8601 text, indexed.
- Unique constraint on `(channel_id, telegram_message_id)`.

Indexes:

- `ix_posts_channel_timestamp` on `(channel_id, timestamp_utc)`.
- `ix_posts_timestamp` on `(timestamp_utc)`.

Timestamps are stored as ISO-8601 UTC strings so lexicographic comparison matches chronological order.

## Concurrency

All MCP tool calls are processed sequentially. The FastMCP server does not run concurrent Telegram or SQLite operations; this simplifies ordering and rate-limit handling. If throughput becomes a requirement later, this decision can be revisited.

## Data retention

A background purge (triggered at the start of `update_channel` or `update_all_channels`) deletes posts older than a configurable TTL. The default TTL is 90 days and can be overridden with the env var `TGMCPSPY_POST_TTL_DAYS`. Posts are immutable once cached; edits and deletions on Telegram are ignored.

## Event payloads and notifications

The server is purely request/response. No MCP notifications, resource subscriptions, or outbound events are emitted when channels or posts change.

## Private content

Both public and private broadcast channels are cached the same way. Access control is delegated to the Telegram user session; the local cache stores whatever messages the session can read.

## Telegram client wrapper

Class `telegram.TelegramClientWrapper`:

- Built from `telethon.sessions.StringSession`.
- `connect()` checks `is_user_authorized()` and raises `ConfigError` if not.
- `disconnect()` closes the session.
- `get_dialogs()` returns broadcast channels (`is_channel and broadcast`) as `ChannelInfo`.
- `resolve_identifier(identifier)` accepts a username (`letsCode_Dru`) or a `-100...` id and returns `ChannelInfo`.
- `fetch_messages_since(identifier, cutoff)` fetches messages newer than `cutoff` (for the 7-day initial backfill).
- `fetch_messages_after(identifier, min_id)` fetches messages with id greater than `min_id` (for incremental updates).
- Both return `list[MessageInfo]` with `telegram_message_id`, `timestamp_utc`, and `text`.
- High-level calls are wrapped by `_with_flood_wait`, which retries on `FloodWaitError` up to 3 times, sleeping `min(seconds, 60)` per retry.

## Syncing and updating

### `sync_dialogs`

1. Call `client.get_dialogs()`.
2. Filter to broadcast channels.
3. Upsert each channel into `channels` with `is_tracked=True`.
4. Return counts of added/updated channels.

### `update_channel(channel)`

1. Resolve the identifier to a channel row. If not present, resolve via Telegram and insert.
2. If `last_message_id` is `None`:
   - `cutoff = now(UTC) - timedelta(days=7)`
   - `messages = fetch_messages_since(channel, cutoff)`
3. Else:
   - `messages = fetch_messages_after(channel, last_message_id)`
4. Upsert each message into `posts`.
5. Update `last_message_id` and `last_fetched_at` on the channel row.
6. Return `{channel, fetched, last_message_id}`.

### `update_all_channels`

Iterate `list_tracked_channels()` sequentially and call `update_channel` for each. If a channel fails (e.g., rate limit or resolution error), the error is recorded for that channel and iteration continues. The final response contains per-channel results and per-channel errors.

## MCP surface

All tools are async. Tools raise FastMCP exceptions on invalid input, missing configuration, or Telegram failures; they do not return `{ok, error}` envelopes. `list_channel_posts` and `list_all_posts` return the full post text for each match.

Channel identifiers accepted by the tools are:

- Telegram username, e.g. `letsCode_Dru`.
- Numeric channel id, including the `-100...` form.

Tools:

- `list_tracked_channels()`
- `add_channel(channel: str)`
- `remove_channel(channel: str)`
- `sync_dialogs()`
- `update_channel(channel: str)`
- `update_all_channels()`
- `get_post(channel: str, post_id: int)`
- `list_channel_posts(channel: str, start_date: str, end_date: str)`
- `list_all_posts(start_date: str, end_date: str)`

Resources:

- `channel://list`
- `post://{channel}/{post_id}`

Prompt:

- `channel_digest://{channel}` with optional `days: int = 7`.

## Date handling

- `start_date` is parsed as the start of the day in UTC.
- `end_date` is parsed as the end of the day in UTC.
- Both accept `YYYY-MM-DD` or ISO timestamps.
- Query uses inclusive boundaries: `timestamp_utc >= start AND timestamp_utc <= end`.

## Lifespan

`server.py` defines an async FastMCP lifespan:

1. Load config.
2. Create SQLAlchemy engine and initialize schema.
3. Create `TelegramClientWrapper` and connect.
4. Yield `AppContext(config, repository, client)`.
5. On shutdown, disconnect the client and dispose the engine.

Tool handlers retrieve the context via `ctx.request_context.lifespan_context`.

## Error handling

Tools raise specific exceptions rather than returning error envelopes:

- `ConfigError` for missing/invalid configuration.
- `ChannelNotFoundError` for identifiers that cannot be resolved.
- `TelegramError` for Telegram/network failures, including exhausted FloodWait retries.

No bare `except:` blocks. Low-level exceptions are wrapped with `raise ... from e` inside the Telegram wrapper and re-raised as domain exceptions at the tool boundary. FastMCP converts these into standard MCP error responses.

## Logging and leak prevention

- The Telegram session string is loaded from env vars and never logged.
- Post text is never written to logs.
- The SQLite database path is local and configurable; it defaults to `tgmcpspy.db` in the working directory.
- The server binds to `127.0.0.1` by default.

## Testing

- `pytest-asyncio` with `asyncio_mode = "auto"`.
- In-memory SQLite via a test fixture.
- `FakeTelegramClient` implements the wrapper interface deterministically.
- Mock `Context` carries a test `AppContext`.
- Tests cover: config validation, DB upserts/queries, Telegram wrapper resolution and FloodWait retry, every MCP tool, and inclusive date boundaries.

## Tooling changes

- `pyproject.toml`:
  - Add `telethon>=1.35.0` and `sqlalchemy>=2.0.0` to `[project.dependencies]`.
  - Add `pytest-asyncio>=0.23.0` to `[project.optional-dependencies.dev]`.
  - Add `[tool.pytest.ini_options]` `asyncio_mode = "auto"`.
  - Add `[[tool.mypy.overrides]]` `ignore_missing_imports = true` for `telethon.*`.
- `.pre-commit-config.yaml`:
  - Change the `pytest-smoke` hook from `args: [-q, tests/test_smoke.py]` to run the full test suite.
- Delete `tests/test_smoke.py` and the demo handlers in `server.py`.

## Risks

- Session string generation is external; bad/missing credentials fail on startup.
- `sync_dialogs` re-tracks locally removed channels because it mirrors Telegram state.
- Sequential `update_all_channels` may be slow for many subscriptions but avoids rate limits.
