# Spec: Post queries

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the read-only MCP tools that surface already-cached posts:
`get_post`, `list_channel_posts`, and `list_all_posts`, plus how date and
`days` arguments are parsed.

Fetching and storing posts is defined in the `post-cache` spec.

## Requirements

- **R1** The server SHALL provide an MCP tool `get_post(channel, post_id)` returning a single post.
- **R2** The server SHALL provide an MCP tool `list_channel_posts` that accepts exactly one query mode: both `start_date` and `end_date` for an explicit inclusive UTC range, or a positive integer `days` for an inclusive rolling UTC range from `now - days` through `now`. It SHALL reject missing, incomplete, mixed, zero, negative, fractional, boolean, and non-numeric modes before querying or mutating cached data.
- **R3** The server SHALL provide an MCP tool `list_all_posts(start_date, end_date)` returning posts from all tracked conversations within an inclusive UTC date range.
- **R4** Date inputs SHALL accept `YYYY-MM-DD` or ISO timestamps and SHALL be interpreted as UTC.
- **R5** `list_channel_posts` and `list_all_posts` SHALL return the full text of each matching post.

## Scenarios

### Reading posts

#### S1 — Get specific post

```
GIVEN channel A has a cached post with Telegram message id 42
WHEN the MCP client calls get_post("A", 42)
THEN the response contains that post's text and timestamp
```

#### S2 — Get missing post

```
GIVEN channel A has no cached post with Telegram message id 99
WHEN the MCP client calls get_post("A", 99)
THEN the tool raises a not-found exception
```

#### S3 — List channel posts by date range

```
GIVEN channel A has cached posts on 2026-07-15, 2026-07-18, and 2026-07-22
WHEN the MCP client calls list_channel_posts("A", "2026-07-14", "2026-07-19")
THEN the response contains the posts from 2026-07-15 and 2026-07-18
  AND does not contain the post from 2026-07-22
```

#### S4 — List all posts by date range

```
GIVEN channels A and B are tracked
  AND A has a post on 2026-07-16
  AND B has a post on 2026-07-17
  AND an untracked channel C has a post on 2026-07-16
WHEN the MCP client calls list_all_posts("2026-07-14", "2026-07-19")
THEN the response contains posts from A and B
  AND does not contain the post from C
```

#### S5 — Full text in lists

```
GIVEN channel A has a cached post with text "Hello, world!"
WHEN the MCP client calls list_channel_posts("A", start, end)
THEN the response includes the full text "Hello, world!"
```

#### S6 — Unknown channel

```
GIVEN no channel named "nonexistent" can be resolved on Telegram
WHEN the MCP client calls update_channel("nonexistent")
THEN the tool raises a channel-not-found exception
```

### Range modes

#### S7 — Rolling days post range

```
GIVEN the current time is 2026-07-23T12:00:00Z
  AND the conversation has posts exactly at 2026-07-20T12:00:00Z, inside the interval, and after the current time
WHEN the MCP client calls list_channel_posts with days=3
THEN posts from the inclusive interval 2026-07-20T12:00:00Z through 2026-07-23T12:00:00Z are returned
  AND posts outside that interval are excluded
```

#### S8 — Explicit post range remains available

```
WHEN the MCP client calls list_channel_posts with valid start_date and end_date and no days
THEN it returns posts using the existing inclusive UTC range behavior
```

#### S9 — Invalid post range modes are rejected

```
WHEN list_channel_posts is called without a mode, with only one explicit date boundary, with explicit boundaries and days together, or with invalid days
THEN the tool raises an MCP error
  AND cached data is not queried or mutated
```