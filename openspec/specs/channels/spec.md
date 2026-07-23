# Spec: Telegram conversation post cache

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the behavior of the `tg-mcp-spy` MCP server with respect to Telegram conversations (direct messages, legacy group chats, broadcast channels, and supergroups), message caching, and the legacy channel-named MCP tool surface.

## Requirements

- **R1** The server SHALL read Telegram credentials from environment variables: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`.
- **R2** The server SHALL use Telethon with a `StringSession` to connect as a Telegram user.
- **R3** The server SHALL fail fast on startup if the session is not authorized.
- **R4** The server SHALL provide an MCP tool `sync_dialogs` that fetches every conversation in the user's Telegram dialog list and marks it as tracked in the local cache.
- **R5** The server SHALL provide an MCP tool `list_tracked_channels` returning all locally tracked conversations and their kinds.
- **R6** The server SHALL provide MCP tools `add_channel(channel)` and `remove_channel(channel)` that update only the local tracked flag, not the user's Telegram subscriptions or memberships.
- **R7** The server SHALL provide an MCP tool `update_channel(channel)` that fetches posts for any tracked conversation.
- **R8** The server SHALL provide an MCP tool `update_all_channels` that updates every tracked conversation sequentially.
- **R9** For a conversation seen for the first time, `update_channel` SHALL fetch posts from the last 7 days.
- **R10** For a conversation already in cache, `update_channel` SHALL fetch only posts newer than the newest cached post.
- **R11** The server SHALL persist cached conversations and posts in a SQLite database.
- **R12** A cached post SHALL contain at minimum: Telegram message id, conversation identifier, UTC timestamp, and text.
- **R13** The server SHALL provide an MCP tool `get_post(channel, post_id)` returning a single post.
- **R14** The server SHALL provide an MCP tool `list_channel_posts(channel, start_date, end_date)` returning posts from one conversation within an inclusive UTC date range.
- **R15** The server SHALL provide an MCP tool `list_all_posts(start_date, end_date)` returning posts from all tracked conversations within an inclusive UTC date range.
- **R16** Date inputs SHALL accept `YYYY-MM-DD` or ISO timestamps and SHALL be interpreted as UTC.
- **R17** The server SHALL retry on `FloodWaitError` up to 3 times with a capped sleep.
- **R18** Tool calls SHALL be processed sequentially.
- **R19** The server SHALL NOT emit MCP notifications or resource-subscription events.
- **R20** Tools SHALL accept identifiers that Telethon resolves to a `User`, `Chat`, or `Channel`, including Telegram usernames and numeric ids (positive user ids, negative legacy-chat ids, and `-100...` channel or supergroup ids).
- **R21** `list_channel_posts` and `list_all_posts` SHALL return the full text of each matching post.
- **R22** `update_all_channels` SHALL continue updating remaining conversations when one conversation fails and SHALL report per-conversation results and errors.
- **R23** The server SHALL cache content from both public and private broadcast channels the same way.
- **R24** Tool errors SHALL be surfaced by raising FastMCP exceptions, not by returning `{ok, error}` envelopes.
- **R25** The server SHALL purge cached posts older than a configurable TTL (default 90 days).
- **R26** Cached posts SHALL be treated as immutable; edits and deletions on Telegram SHALL be ignored.
- **R27** Every cached conversation SHALL carry a `kind` field with value `channel`, `chat`, or `user`.
- **R28** `sync_dialogs` SHALL mirror every conversation in the user's Telegram dialog list (DMs, legacy chats, and channels), not only broadcast channels.
- **R29** `add_channel(channel)` SHALL accept identifiers that resolve to a `User`, `Chat`, or `Channel` entity on Telegram.
- **R30** `update_channel` and `update_all_channels` SHALL fetch and cache posts from any tracked `User`, `Chat`, or `Channel`.
- **R31** The server SHALL persist the conversation kind in a dedicated SQLite column with default value `channel` so existing rows remain valid without a manual migration step.
- **R32** First-add backfill SHALL remain at 7 days for every kind.

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

### Broadened conversation support

#### S21 — Sync dialogs includes DMs and groups

```
GIVEN the server is configured with a valid Telegram user session
  AND the user has a direct message dialog with user U
  AND a legacy small-group chat dialog C
  AND a broadcast-channel dialog B
WHEN the MCP client calls sync_dialogs
THEN the response includes U, C, and B
  AND U is marked with kind="user"
  AND C is marked with kind="chat"
  AND B is marked with kind="channel"
```

#### S22 — Add user by numeric id

```
GIVEN the user has access to user U with Telegram id 6199205118
WHEN the MCP client calls add_channel("6199205118")
THEN U is added to the tracked list with kind="user"
  AND the user's Telegram subscription is unchanged
```

#### S23 — Add legacy chat by id

```
GIVEN the user is a member of legacy chat C with a negative id
WHEN the MCP client calls add_channel("-123456789")
THEN C is added to the tracked list with kind="chat"
```

#### S24 — Add supergroup by id

```
GIVEN the user is a member of supergroup S with id -1001234567890
WHEN the MCP client calls add_channel("-1001234567890")
THEN S is added to the tracked list with kind="channel"
```

### Fetching beyond channels

#### S25 — Update tracks DM, chat, and channel uniformly

```
GIVEN U (user), C (chat), and B (channel) are tracked
  AND each has unread messages since last update
WHEN the MCP client calls update_all_channels
THEN U, C, and B are each updated sequentially
  AND the response contains per-conversation fetched counts and the kind
```

#### S26 — First-add backfill is 7 days for every kind

```
GIVEN U (a user DM) has never been updated
  AND U has 2 messages within the last 7 days and 1 older message
WHEN the MCP client calls update_channel("U")
THEN exactly those 2 recent messages are cached
```

### Backward compatibility

#### S27 — Existing rows default to kind="channel"

```
GIVEN the SQLite database contains rows inserted before this change
WHEN the server starts
THEN those rows are read successfully with kind="channel"
  AND the server can resolve, update, and list them as before
```

## Notes

- All data is fetched through the Telegram API (Telethon user session); no web scraping.
- Add/remove channel tools affect only the local tracked state and do not subscribe, unsubscribe, join, leave, or delete anything on Telegram.
- Public dataclass, exception, and MCP tool names retain the legacy word `channel`; in this API, “channel” means any tracked conversation.
- `User`, legacy `Chat`, and `Channel` entities are distinguished by `kind=user|chat|channel` and resolved through the corresponding Telethon peer type.
- Existing database rows default to `kind="channel"`; no manual migration is required.
- The minimal post model stores id, conversation reference, timestamp, and text. Media and rich metadata are intentionally out of scope.
