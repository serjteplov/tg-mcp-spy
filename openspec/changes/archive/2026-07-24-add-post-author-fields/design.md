# Design: Add post author fields (`username`, `display_name`)

## Technical approach

### 1. Domain model (`src/package_tgmcpspy/models.py`)

`MessageInfo` and `Post` gain two new optional fields, both defaulting to
`None` so existing construction sites do not break:

```python
username: str | None = None
display_name: str | None = None
```

Both dataclasses stay `frozen=True`. Field order puts the identifiers
(id, channel_id, telegram_message_id, text, timestamp_utc) before the new
author fields so existing asdict output grows at the end.

### 2. Storage (`src/package_tgmcpspy/db.py`)

The `posts` table gets two new nullable columns and one new index:

```python
Column("username", String, nullable=True),
Column("display_name", String, nullable=True),
Index("ix_posts_display_name", "display_name"),
```

`_upgrade_schema` adds a row to the existing `upgrades` list that performs
an idempotent `ALTER TABLE posts ADD COLUMN` for each column, using the
same `PRAGMA table_info` guard already present for `kind`.

`_row_to_post` reads `username` and `display_name` from the row mapping and
passes them to `Post(...)`.

`_SyncRepository.upsert_posts` includes the two fields in the values
dictionary it passes to `conn.execute(posts_table.insert(), [...])`.

### 3. Telegram fetch helpers (`src/package_tgmcpspy/telegram.py`)

A small private helper composes the two values from a Telethon `Message`:

```python
def _sender_fields(message: Message) -> tuple[str | None, str | None]:
    if getattr(message, "action", None) is not None:
        return None, None
    sender = getattr(message, "sender", None)
    if sender is None or getattr(sender, "deleted", False):
        return None, None
    if not isinstance(sender, User):
        return None, None
    username = sender.username or None
    first_last = " ".join(
        part for part in (sender.first_name or "", sender.last_name or "") if part
    )
    display_name = first_last or username
    return username, display_name
```

`fetch_messages_since` and `fetch_messages_after` call the helper and pass
the result to `MessageInfo(...)`. The helper is a pure function over the
Telegram `Message` object; it is unit-tested without any I/O.

### 4. Server output (`src/package_tgmcpspy/server.py`)

No changes. `_post_to_dict` already uses `asdict(post)`, so the two new
keys appear automatically in the JSON response.

### 5. Tests

- `tests/test_db.py`
  - Round-trip: insert a post with both fields populated, read it back,
    assert equality.
  - Round-trip with both fields `None`: insert a post with neither field
    set, read it back, assert equality.
  - Schema upgrade: create a `posts` table without the new columns,
    call `init_schema`, assert columns + index exist.
- `tests/test_telegram.py`
  - Unit tests for `_sender_fields` covering: real name + username,
    real name only, username only, neither, service message, deleted
    sender, non-User sender.
  - `fetch_messages_since` / `fetch_messages_after` map mocked Telethon
    `Message` objects correctly into `MessageInfo` with the new fields.
- `tests/test_server.py`
  - `get_post` payload contains `username` and `display_name` keys.
  - `list_channel_posts` outputs include the new keys.

### 6. Migration behavior

- Existing rows: `username` and `display_name` are `NULL` after the
  `ALTER TABLE` runs. No backfill is performed (consistent with R26).
- New posts: populated from the moment `update_channel` or
  `update_all_channels` runs against the new code.

## Alternatives considered

- **Store `sender_id` (int) instead of `display_name` (str).** Rejected:
  keeps the field numeric and requires a separate resolution step on read
  to produce a human name. The agreed semantics favor a string display
  name directly.
- **Add a separate `sender_id` integer column alongside `display_name`.**
  Rejected for now: out of scope per the agreed plan. Can be added later
  if a future requirement needs the numeric id.
- **Resolve senders via `get_entity` on the fetch path.** Rejected: adds N
  Telegram round-trips per update, increasing rate-limit risk and update
  latency. Rely on Telethon's already-resolved `Message.sender`.
- **Backfill existing rows.** Rejected: violates the immutability rule
  (R26) and would require re-fetching historical messages from Telegram.
- **Lazy computation on read.** Rejected: complicates the `Post` API
  (callers would need to pass a resolver). The values are simple enough
  to denormalize at write time.
