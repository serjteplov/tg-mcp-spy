# Spec: MCP resources

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the read-only MCP resources exposed by the server for
tracked conversations and cached posts: a tracked-list resource, a
single-post resource template, and two post-list resource templates
(rolling `days` and explicit `start_date`/`end_date`). All resources
read only the local SQLite cache and never contact Telegram.

## Requirements

- **R1** The server SHALL expose `channel://list` as a live read-only MCP resource. It SHALL return a JSON array containing all locally tracked conversations and SHALL exclude untracked conversations. Each channel object SHALL use the same serialization as `list_tracked_channels`, including `kind` and `groups`.
- **R2** The server SHALL expose `post://{channel}/{post_id}` as a live read-only MCP resource template. It SHALL resolve `channel` only against cached Telegram IDs or cached usernames, retrieve the cached Telegram message ID identified by `post_id`, and return the same serialized post fields as `get_post`.
- **R3** The server SHALL expose `posts://{channel}/recent/{days}` as a live read-only MCP resource template. It SHALL return the full serialized cached posts in the inclusive rolling UTC interval from `now - days` through `now`, ordered by UTC timestamp ascending. `days` SHALL follow the same positive-integer validation as the `list_channel_posts` tool.
- **R4** The server SHALL expose `posts://{channel}/range/{start_date}/{end_date}` as a live read-only MCP resource template. It SHALL accept `YYYY-MM-DD` and ISO timestamp boundaries, interpret them as UTC, apply the existing inclusive explicit-range semantics, and return full serialized posts ordered by timestamp ascending.
- **R5** All resources SHALL read only the local SQLite cache. They SHALL NOT refresh conversations, resolve identifiers through Telegram, mutate tracking or group membership, emit notifications, or return `{ok, error}` envelopes. Existing read tools SHALL remain available with their existing call signatures.

## Scenarios

### Tracked-list resource

#### S1 — Read tracked conversations as a resource

```
GIVEN conversations A and B are tracked
  AND conversation B has groups ["tech"]
  AND cached conversation C is not tracked
WHEN an MCP client reads channel://list
THEN the resource has media type application/json
  AND its JSON array contains A and B
  AND B has groups=["tech"]
  AND it does not contain C
```

#### S2 — Read an empty tracked list

```
GIVEN no conversation is tracked
WHEN an MCP client reads channel://list
THEN the resource returns an empty JSON array
  AND it does not contact Telegram
```

### Single-post resource template

#### S3 — Read one cached post

```
GIVEN cached conversation A has Telegram ID 100 and username "alpha"
  AND A has cached post 42 with sender and timestamp fields
WHEN an MCP client reads post://alpha/42
THEN the resource has media type application/json
  AND the JSON object matches get_post("alpha", 42)
  AND it includes username and display_name keys
```

#### S4 — Resolve a numeric cached identifier locally

```
GIVEN cached conversation A has Telegram ID 100
  AND A has cached post 42
WHEN an MCP client reads post://100/42
THEN the resource returns post 42
  AND it performs no Telegram I/O
```

#### S5 — Reject an unknown cached conversation

```
GIVEN no cached conversation matches "unknown"
WHEN an MCP client reads post://unknown/42
THEN the resource raises ChannelNotFoundError as an MCP error
  AND it does not ask Telegram to resolve "unknown"
```

#### S6 — Reject a missing cached post

```
GIVEN conversation A is cached
  AND A has no cached post 99
WHEN an MCP client reads post://A/99
THEN the resource raises ChannelNotFoundError as an MCP error
```

### Recent posts resource template

#### S7 — Read recent cached posts

```
GIVEN the current time is 2026-07-25T12:00:00Z
  AND conversation A has posts at 2026-07-22T12:00:00Z, 2026-07-24T12:00:00Z,
     and 2026-07-26T12:00:00Z
WHEN an MCP client reads posts://A/recent/3
THEN the resource has media type application/json
  AND it contains the posts at 2026-07-22T12:00:00Z and 2026-07-24T12:00:00Z
  AND it excludes the future post
  AND results are ordered oldest first
```

#### S8 — Reject invalid recent days

```
WHEN an MCP client requests the recent-post resource with zero, a negative
    value, a fractional value, a boolean-like value, or a non-numeric value
THEN the resource raises ConfigError as an MCP error
  AND it does not query posts or contact Telegram
```

### Explicit-range posts resource template

#### S9 — Read an explicit cached-post range

```
GIVEN conversation A has cached posts on 2026-07-15, 2026-07-18, and 2026-07-22
WHEN an MCP client reads posts://A/range/2026-07-14/2026-07-19
THEN the resource has media type application/json
  AND it contains the posts from 2026-07-15 and 2026-07-18
  AND it excludes the post from 2026-07-22
```

#### S10 — Reject an invalid explicit boundary

```
WHEN an MCP client supplies an invalid start_date or end_date in the range URI
THEN the resource raises ConfigError as an MCP error
  AND it does not contact Telegram
```

### Cross-cutting guarantees

#### S11 — Resource read does not refresh stale data

```
GIVEN conversation A is cached but has newer posts on Telegram
WHEN an MCP client reads any resource for A
THEN only currently cached data is returned
  AND update_channel is not invoked
  AND Telegram is not contacted
```

#### S12 — Existing read tools remain available

```
WHEN an MCP client enumerates tools after this change
THEN list_tracked_channels, get_post, list_channel_posts, and list_all_posts are
    still present
```