# Spec: Post cache

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines how Telegram posts are fetched, persisted, and aged in the
local cache: incremental vs. first-update backfill, retention TTL,
immutability, equal handling for public and private channels, and the
nullable per-message sender fields (`username`, `display_name`).

Reading already-cached posts is defined in the `post-queries` spec.

## Requirements

- **R1** For a conversation without prior update state, `update_channel` SHALL fetch posts from the configured number of previous days, defaulting to 7 days.
- **R2** For a conversation already in cache, `update_channel` SHALL fetch only posts newer than the newest cached post.
- **R3** The server SHALL persist cached conversations and posts in a SQLite database.
- **R4** A cached post SHALL contain at minimum: Telegram message id, conversation identifier, UTC timestamp, text, and the sender's `username` and `display_name` (both nullable).
- **R5** The server SHALL purge cached posts older than a configurable TTL (default 90 days).
- **R6** Cached posts SHALL be treated as immutable; edits and deletions on Telegram SHALL be ignored.
- **R7** The server SHALL cache content from both public and private broadcast channels the same way.
- **R8** `update_all_channels` SHALL continue updating remaining conversations when one conversation fails and SHALL report per-conversation results and errors.
- **R9** A cached post SHALL carry two per-message sender fields populated from Telethon's already-resolved `Message.sender` at the time of fetch: `username` (the sender's Telegram public `@username` without the leading `@`) and `display_name` (the sender's `first_name + last_name`, trimmed and joined with a single space, falling back to `username` when neither name is present). Both fields are nullable.
- **R10** Both `username` and `display_name` SHALL be `NULL` for messages where the sender cannot be identified as a regular Telegram `User`: broadcast-channel posts (anonymous admin / channel-post), service messages (`message.action is not None`), senders marked as deleted (`sender.deleted is True`), and messages where `message.sender` is `None` even if `sender_id` is set.
- **R11** The `posts` table SHALL have an index on `display_name` to support future per-author lookups without a schema change.
- **R12** `get_post`, `list_channel_posts`, and `list_all_posts` SHALL include `username` and `display_name` in their response payload via the existing `asdict(post)` serialization. The keys are present in every post and MAY be `null`.

## Scenarios

### Fetching and caching

#### S1 — Initial backfill

```
GIVEN channel A has never been updated
  AND TGMCPSPY_BACKFILL_DAYS is absent or set to 7
  AND channel A has 3 posts in the last 7 days and 5 older posts
WHEN the MCP client calls update_channel("A")
THEN exactly those 3 recent posts are cached
  AND the channel's last_message_id equals the newest cached message id
```

#### S2 — Incremental update

```
GIVEN channel A was previously updated and its last_message_id is 100
  AND channel A has 2 new posts with ids 101 and 102
WHEN the MCP client calls update_channel("A")
THEN only posts 101 and 102 are added to the cache
```

#### S3 — Update tracks DM, chat, and channel uniformly

```
GIVEN U (user), C (chat), and B (channel) are tracked
  AND each has unread messages since last update
WHEN the MCP client calls update_all_channels
THEN U, C, and B are each updated sequentially
  AND the response contains per-conversation fetched counts and the kind
```

#### S4 — Partial failure in update_all_channels

```
GIVEN channels A, B, and C are tracked
  AND updating B triggers a Telegram rate limit that exhausts retries
WHEN the MCP client calls update_all_channels
THEN A and C are updated successfully
  AND the response contains an error entry for B
```

#### S5 — Immutability and TTL

```
GIVEN channel A has a cached post from 100 days ago
  AND the configured TTL is 90 days
WHEN update_channel("A") runs
THEN the 100-day-old post is removed from the cache
  AND if that post is later edited on Telegram, the cached version is not updated
```

#### S6 — Private channel content

```
GIVEN the user has access to private channel P
  AND P is tracked
WHEN update_channel("P") runs
THEN posts from P are cached the same way as public channel posts
```

### Post author fields

#### S7 — Group post with real name and username

```
GIVEN channel A is a supergroup
  AND user U (telegram_id=42, first_name="Alice", last_name="Smith",
    username="alice") sends a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username="alice" AND
  display_name="Alice Smith"
```

#### S8 — Channel post with no resolved user sender

```
GIVEN channel A is a broadcast channel
  AND an anonymous admin posts a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username=NULL AND display_name=NULL
```

#### S9 — Service message has no author fields

```
GIVEN channel A has a service message M (e.g. a member-joined event)
WHEN update_channel("A") caches M
THEN the cached row for M has username=NULL AND display_name=NULL
```

#### S10 — Sender with username but no real name

```
GIVEN user U (telegram_id=42, first_name=NULL, last_name=NULL,
    username="bob") sends a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username="bob" AND display_name="bob"
```

#### S11 — Schema upgrade on an existing database

```
GIVEN an existing SQLite database with a posts table that lacks
  `username` and `display_name` columns
WHEN the server starts against that database
THEN init_schema adds the two columns AND the index ix_posts_display_name
  AND existing rows are read with username=NULL and display_name=NULL
```