# Delta Spec: Add post author fields (`username`, `display_name`)

## MODIFIED Requirements

### R12 — Cached post content

The text of R12 is updated so that the set of "at minimum" fields grows
from four to six. The original text reads:

> A cached post SHALL contain at minimum: Telegram message id, conversation
> identifier, UTC timestamp, and text.

The new text reads:

> A cached post SHALL contain at minimum: Telegram message id, conversation
> identifier, UTC timestamp, text, and the sender's `username` and
> `display_name` (both nullable).

### T-SQL / schema migration

The existing `kind` migration in `_upgrade_schema` is the template for the
new columns. The change adds two new rows to the `upgrades` list:

- `("posts", "username", "VARCHAR")`
- `("posts", "display_name", "VARCHAR")`

Both columns are nullable. No backfill is performed; existing rows default
to `NULL`.

## ADDED Requirements

### R-NEW-1 — Per-message sender fields

A cached post SHALL carry two sender fields populated from Telethon's
already-resolved `Message.sender` at the time of fetch:

- `username`: the sender's Telegram public `@username` (without the leading
  `@`). `NULL` when the sender has no public username or is not a user.
- `display_name`: the sender's human-friendly display name. When
  `first_name` or `last_name` is present, the value is
  `f"{first_name} {last_name}".strip()` with a single space between the
  parts. When neither is present, the value is the `username`. When
  no display name can be derived, the value is `NULL`.

### R-NEW-2 — Sender resolution rules

Both `username` and `display_name` SHALL be `NULL` for messages where the
sender cannot be identified as a regular Telegram `User`:

- broadcast-channel posts (anonymous admin / channel-post, where Telethon
  does not resolve a `User` sender);
- service messages (`message.action is not None`);
- senders marked as deleted (`sender.deleted is True`);
- messages where `message.sender` is `None` even if `sender_id` is set.

### R-NEW-3 — Index on display name

The `posts` table SHALL have an index on `display_name` to support future
per-author lookups without a schema change.

### R-NEW-4 — Tool output exposes the new fields

`get_post`, `list_channel_posts`, and `list_all_posts` SHALL include
`username` and `display_name` in their response payload via the existing
`asdict(post)` serialization. The keys are present in every post and MAY
be `null`.

## ADDED Scenarios

### S-NEW-1 — Group post with real name and username

```
GIVEN channel A is a supergroup
  AND user U (telegram_id=42, first_name="Alice", last_name="Smith",
    username="alice") sends a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username="alice" AND
  display_name="Alice Smith"
```

### S-NEW-2 — Channel post with no resolved user sender

```
GIVEN channel A is a broadcast channel
  AND an anonymous admin posts a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username=NULL AND display_name=NULL
```

### S-NEW-3 — Service message has no author fields

```
GIVEN channel A has a service message M (e.g. a member-joined event)
WHEN update_channel("A") caches M
THEN the cached row for M has username=NULL AND display_name=NULL
```

### S-NEW-4 — Sender with username but no real name

```
GIVEN user U (telegram_id=42, first_name=NULL, last_name=NULL,
    username="bob") sends a message M
WHEN update_channel("A") caches M
THEN the cached row for M has username="bob" AND display_name="bob"
```

### S-NEW-5 — MCP tool output contains the new fields

```
GIVEN channel A has a cached post with username="alice" and
  display_name="Alice Smith"
WHEN the MCP client calls get_post("A", post_id)
THEN the response JSON contains the keys "username" and "display_name"
  AND their values equal "alice" and "Alice Smith"
```

### S-NEW-6 — Schema upgrade on an existing database

```
GIVEN an existing SQLite database with a posts table that lacks
  `username` and `display_name` columns
WHEN the server starts against that database
THEN init_schema adds the two columns AND the index ix_posts_display_name
  AND existing rows are read with username=NULL and display_name=NULL
```
