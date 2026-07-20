# tg-mcp-spy

A Python MCP (Model Context Protocol) server that caches Telegram channel posts in a local SQLite database and exposes them via MCP tools. It connects to Telegram through a user session (Telethon) and mirrors the user's broadcast-channel subscriptions into a queryable local cache.

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

The session string must be generated externally (e.g. via Telethon's interactive login). Optional variables:

| Variable | Default | Description |
|---|---|---|
| `TGMCPSPY_DB_PATH` | `tgmcpspy.db` | Path to the SQLite database |
| `TGMCPSPY_POST_TTL_DAYS` | `90` | Days to retain cached posts |

### 3. Run the server

```bash
python -m package_tgmcpspy.server
```

The server binds to `127.0.0.1:8000` by default.

## MCP Tools

| Tool | Description |
|---|---|
| `list_tracked_channels` | List all locally tracked channels |
| `add_channel(channel)` | Add a channel to the local tracked list |
| `remove_channel(channel)` | Remove a channel from the local tracked list |
| `sync_dialogs` | Sync tracked channels with your Telegram subscriptions |
| `update_channel(channel)` | Fetch latest posts for a single channel |
| `update_all_channels` | Fetch latest posts for all tracked channels |
| `get_post(channel, post_id)` | Get a specific cached post |
| `list_channel_posts(channel, start_date, end_date)` | List posts from one channel by date range |
| `list_all_posts(start_date, end_date)` | List posts from all tracked channels by date range |

Channel identifiers accept a Telegram username or numeric id (including `-100...` format). Dates accept `YYYY-MM-DD` or ISO timestamps, interpreted as UTC.

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
