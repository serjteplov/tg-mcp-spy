# Delta spec: Telegram channel post cache

## Status

DRAFT — pending implementation and review.

## Scope

This delta defines the behavior of the `tg-mcp-spy` MCP server with respect to Telegram channel subscriptions, post caching, and the MCP tool surface.

## Requirements

### ADDED

- **R1** The server SHALL read Telegram credentials from environment variables: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`.
- **R2** The server SHALL use Telethon with a `StringSession` to connect as a Telegram user.
- **R3** The server SHALL fail fast on startup if the session is not authorized.
- **R4** The server SHALL provide an MCP tool `sync_dialogs` that fetches the user's broadcast-channel dialogs and marks them as tracked in the local cache.
- **R5** The server SHALL provide an MCP tool `list_tracked_channels` returning all locally tracked channels.
- **R6** The server SHALL provide MCP tools `add_channel(channel)` and `remove_channel(channel)` that update only the local tracked flag, not the user's Telegram subscriptions.
- **R7** The server SHALL provide an MCP tool `update_channel(channel)` that fetches posts for that channel.
- **R8** The server SHALL provide an MCP tool `update_all_channels` that updates every tracked channel sequentially.
- **R9** For a channel seen for the first time, `update_channel` SHALL fetch posts from the last 7 days.
- **R10** For a channel already in cache, `update_channel` SHALL fetch only posts newer than the newest cached post.
- **R11** The server SHALL persist cached channels and posts in a SQLite database.
- **R12** A cached post SHALL contain at minimum: Telegram message id, channel identifier, UTC timestamp, and text.
- **R13** The server SHALL provide an MCP tool `get_post(channel, post_id)` returning a single post.
- **R14** The server SHALL provide an MCP tool `list_channel_posts(channel, start_date, end_date)` returning posts from one channel within an inclusive UTC date range.
- **R15** The server SHALL provide an MCP tool `list_all_posts(start_date, end_date)` returning posts from all tracked channels within an inclusive UTC date range.
- **R16** Date inputs SHALL accept `YYYY-MM-DD` or ISO timestamps and SHALL be interpreted as UTC.
- **R17** The server SHALL retry on `FloodWaitError` up to 3 times with a capped sleep.
- **R18** Tool calls SHALL be processed sequentially.
- **R19** The server SHALL NOT emit MCP notifications or resource-subscription events.
- **R20** Tools SHALL accept channel identifiers as either a Telegram username or a numeric channel id (including `-100...`).
- **R21** `list_channel_posts` and `list_all_posts` SHALL return the full text of each matching post.
- **R22** `update_all_channels` SHALL continue updating remaining channels when one channel fails and SHALL report per-channel results and errors.
- **R23** The server SHALL cache content from both public and private broadcast channels the same way.
- **R24** Tool errors SHALL be surfaced by raising FastMCP exceptions, not by returning `{ok, error}` envelopes.
- **R25** The server SHALL purge cached posts older than a configurable TTL (default 90 days).
- **R26** Cached posts SHALL be treated as immutable; edits and deletions on Telegram SHALL be ignored.

### MODIFIED

- **M1** The existing demo handlers (`add`, `greeting`, `greet_user`) and their tests SHALL be removed.
- **M2** The `pytest-smoke` pre-commit hook SHALL run the full test suite instead of `tests/test_smoke.py`.

### REMOVED

- None.

## Scenarios

### Channel tracking

#### S1 — Sync dialogs from Telegram

```
GIVEN the server is configured with a valid Telegram user session
  AND the user is subscribed to broadcast channels A and B
WHEN the MCP client calls sync_dialogs
THEN the response indicates success
  AND both A and B are marked as tracked in the local cache
```

#### S2 — List tracked channels

```
GIVEN channels A and B are tracked
  AND channel C is not tracked
WHEN the MCP client calls list_tracked_channels
THEN the response contains A and B
  AND the response does not contain C
```

#### S3 — Remove channel locally

```
GIVEN channel A is tracked
WHEN the MCP client calls remove_channel("A")
THEN channel A is no longer tracked
  AND the user's Telegram subscription to A is unchanged
```

#### S4 — Add channel locally

```
GIVEN channel D exists on Telegram but is not tracked
WHEN the MCP client calls add_channel("D")
THEN channel D becomes tracked
  AND the user's Telegram subscription to D is unchanged
```

### Fetching and caching

#### S5 — Initial backfill

```
GIVEN channel A has never been updated
  AND channel A has 3 posts in the last 7 days and 5 older posts
WHEN the MCP client calls update_channel("A")
THEN exactly those 3 recent posts are cached
  AND the channel's last_message_id equals the newest cached message id
```

#### S6 — Incremental update

```
GIVEN channel A was previously updated and its last_message_id is 100
  AND channel A has 2 new posts with ids 101 and 102
WHEN the MCP client calls update_channel("A")
THEN only posts 101 and 102 are added to the cache
```

#### S7 — Update all channels

```
GIVEN channels A and B are tracked
  AND both have new posts since their last update
WHEN the MCP client calls update_all_channels
THEN A and B are updated sequentially
  AND the response contains per-channel fetched counts
```

### Reading posts

#### S8 — Get specific post

```
GIVEN channel A has a cached post with Telegram message id 42
WHEN the MCP client calls get_post("A", 42)
THEN the response contains that post's text and timestamp
```

#### S9 — Get missing post

```
GIVEN channel A has no cached post with Telegram message id 99
WHEN the MCP client calls get_post("A", 99)
THEN the tool raises a not-found exception
```

#### S10 — List channel posts by date range

```
GIVEN channel A has cached posts on 2026-07-15, 2026-07-18, and 2026-07-22
WHEN the MCP client calls list_channel_posts("A", "2026-07-14", "2026-07-19")
THEN the response contains the posts from 2026-07-15 and 2026-07-18
  AND does not contain the post from 2026-07-22
```

#### S11 — List all posts by date range

```
GIVEN channels A and B are tracked
  AND A has a post on 2026-07-16
  AND B has a post on 2026-07-17
  AND an untracked channel C has a post on 2026-07-16
WHEN the MCP client calls list_all_posts("2026-07-14", "2026-07-19")
THEN the response contains posts from A and B
  AND does not contain the post from C
```

### Errors and edge cases

#### S12 — Unauthorized session

```
GIVEN the configured Telegram session string is invalid or expired
WHEN the server starts or connects
THEN startup fails with a clear authorization error
```

#### S13 — Unknown channel

```
GIVEN no channel named "nonexistent" can be resolved on Telegram
WHEN the MCP client calls update_channel("nonexistent")
THEN the tool raises a channel-not-found exception
```

#### S14 — Flood wait handling

```
GIVEN a Telegram call raises FloodWaitError with 5 seconds
WHEN the server retries the call
THEN it waits up to the requested time and succeeds within 3 retries
```

### Concurrency, events, and edge cases

#### S15 — Sequential processing

```
GIVEN two MCP clients call update_channel("A") and update_channel("B") at the same time
WHEN the server handles the calls
THEN the two updates run one after another, not in parallel
```

#### S16 — No notifications

```
GIVEN update_channel("A") adds new posts to the cache
WHEN the update completes
THEN the server does not emit any MCP notification or resource-subscription event
```

#### S17 — Partial failure in update_all_channels

```
GIVEN channels A, B, and C are tracked
  AND updating B triggers a Telegram rate limit that exhausts retries
WHEN the MCP client calls update_all_channels
THEN A and C are updated successfully
  AND the response contains an error entry for B
```

#### S18 — Immutability and TTL

```
GIVEN channel A has a cached post from 100 days ago
  AND the configured TTL is 90 days
WHEN update_channel("A") runs
THEN the 100-day-old post is removed from the cache
  AND if that post is later edited on Telegram, the cached version is not updated
```

#### S19 — Full text in lists

```
GIVEN channel A has a cached post with text "Hello, world!"
WHEN the MCP client calls list_channel_posts("A", start, end)
THEN the response includes the full text "Hello, world!"
```

#### S20 — Private channel content

```
GIVEN the user has access to private channel P
  AND P is tracked
WHEN update_channel("P") runs
THEN posts from P are cached the same way as public channel posts
```

## Notes

- The initial requirement mentioned scraping `https://t.me/s/<channel>` and paginating with `?before=<post_id>`. After clarification, all data is fetched through the Telegram API; therefore `t.me/s` scraping is not part of this delta.
- Add/remove channel tools affect only the local cache and do not subscribe or unsubscribe the user on Telegram.
- The minimal post model stores id, channel, timestamp, and text. Media and rich metadata are intentionally out of scope.
