# tg-mcp-spy

A Python MCP (Model Context Protocol) server that caches Telegram conversations (channels, group chats, and direct messages) in a local SQLite database and exposes them via MCP tools. It connects to Telegram through a user session (Telethon) and mirrors the user's dialogs into a queryable local cache.

## Quick start

### 1. Install dependencies

```bash
uv sync --all-extras
```

### 2. Set environment variables

```bash
export TELEGRAM_API_ID=your_api_id
export TELEGRAM_API_HASH=your_api_hash
export TELEGRAM_SESSION_STRING=your_session_string
```
#### How to get ids
sudo nano /etc/hosts  
149.154.167.220 my.telegram.org
sudo resolvectl flush-caches
go to https://my.telegram.org/ and create the app
revert /etc/hosts changes
python src/package_tgmcpspy/obtain_session.py

The session string must be generated externally (e.g. via Telethon's interactive login). Optional variables:

| Variable | Default | Description |
|---|---|---|
| `TGMCPSPY_DB_PATH` | `tgmcpspy.db` | Path to the SQLite database |
| `TGMCPSPY_POST_TTL_DAYS` | `90` | Days to retain cached posts |
| `TGMCPSPY_BACKFILL_DAYS` | `7` | Days of history to fetch on first update for a new conversation |

### 3. Run the server

```bash
npx @modelcontextprotocol/inspector
set -a && source .env && set +a && python -m package_tgmcpspy.server
```
```bash
set -a && source .env && set +a && mcp dev src/package_tgmcpspy/server.py
```

The server binds to `127.0.0.1:8000` by default.

## MCP Tools

| Tool | Description |
|---|---|
| `list_tracked_channels` | List all locally tracked conversations (channel, chat, or user) |
| `add_channel(channel)` | Add a channel/chat/user to the local tracked list |
| `add_channel_batch(channels)` | Add multiple comma-separated channels sequentially with per-item results |
| `remove_channel(channel)` | Remove a tracked conversation from the local tracked list |
| `add_channel_all` | Add every dialog in Telegram (DMs, group chats, channels) to the tracked list |
| `remove_all_channels(confirm)` | Permanently delete all cached conversations and posts (requires `confirm=True`) |
| `update_channel(channel)` | Fetch latest posts for a single conversation |
| `update_all_channels` | Fetch latest posts for all tracked conversations |
| `get_post(channel, post_id)` | Get a specific cached post |
| `list_channel_posts(channel, ...)` | List posts from one conversation by explicit date range or rolling `days` |
| `list_all_posts(start_date, end_date)` | List posts from all tracked conversations by date range |
| `trash_all_messages(confirm)` | Same transactional full-reset as `remove_all_channels` (requires `confirm=True`) |

Tool names keep the legacy `channel`/`add_channel` shape even when the underlying entity is a user or chat — the word "channel" is shorthand for "any tracked conversation".

Identifiers accept a Telegram username, a numeric id (positive for users, negative for legacy chats, `-100...` for channels/supergroups), or a phone number. Telethon resolves the right entity type automatically. Dates accept `YYYY-MM-DD` or ISO timestamps, interpreted as UTC.

`add_channel_all` mirrors *every* dialog in the user's Telegram account — DMs, legacy small-group chats, broadcast channels, and supergroups. If you do not want to track a particular conversation, call `remove_channel` to untrack it locally (this does **not** unsubscribe or delete the dialog on Telegram). `list_channel_posts` accepts either an explicit `start_date`/`end_date` pair or a positive integer `days` (inclusive UTC interval ending now); the two modes cannot be combined.

`remove_all_channels` and `trash_all_messages` are destructive local-cache resets. Both require `confirm=True`; missing or false confirmation raises an error before any database or Telegram I/O. Both run as one transaction and return deletion counts (`posts_deleted`, `channels_deleted`). They do not leave Telegram conversations, modify memberships, or send messages. After a confirmed reset, re-added conversations have no prior update state, so the next `update_channel` will backfill using `TGMCPSPY_BACKFILL_DAYS`.

### Common tool calls

- `add_channel_batch("news, -1001234567890, 12345")` resolves and tracks each identifier sequentially without fetching messages.
- `list_channel_posts(channel="news", days=3)` lists the inclusive rolling UTC range ending now.
- `list_channel_posts(channel="news", start_date="2026-07-20", end_date="2026-07-23")` uses an inclusive explicit UTC date range; do not combine this mode with `days`.
- `remove_all_channels(confirm=True)` or `trash_all_messages(confirm=True)` permanently clears the local cache and returns deletion counts.

## MCP Resources

| URI | Description |
|---|---|
| `channel://list` | Tracked channels (placeholder; use the tool for live data) |
| `post://{channel}/{post_id}` | Single cached post (placeholder; use the tool for live data) |

## MCP Prompt

| URI | Description |
|---|---|
| `channel_digest://{channel}` | Summarize recent posts from a channel (default: last 7 days) |

## Development

```bash
make format    # Format code with ruff
make lint      # Run ruff linter
make typecheck # Run mypy
make test      # Run pytest
make check     # Run format-check + lint + typecheck + test
```

## Architecture

```
src/package_tgmcpspy/
  models.py      — domain dataclasses, exceptions, identifier normalization
  config.py      — environment-based configuration loading
  db.py          — SQLAlchemy Core schema + async repository
  telegram.py    — Telethon wrapper with FloodWait retry
  server.py      — FastMCP application, lifespan, tools, resources, prompts
```

All MCP tool calls are processed sequentially. Cached posts are immutable — edits and deletions on Telegram are ignored. Posts older than the configured TTL are purged automatically.

A tracked conversation carries a `kind` discriminator with value `channel`, `chat`, or `user`, exposed through `list_tracked_channels` and the per-tool responses. Existing rows in `tgmcpspy.db` continue to load without a manual migration step; the server adds the `kind` column automatically and back-fills it with `channel`.
