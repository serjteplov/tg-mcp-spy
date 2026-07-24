# Proposal: Add post author fields (`username`, `display_name`)

## Why

Cached posts in `tg-mcp-spy` expose only the Telegram message id, conversation
identifier, UTC timestamp, and text. Clients must answer "who posted this?"
without re-fetching from Telegram. Today they cannot — the per-message author
information is dropped on the way from Telethon into the SQLite cache.

## What changes

Each cached post SHALL carry two new nullable fields describing the message
sender:

- `username` — the sender's Telegram public `@username` (without the leading
  `@`), populated from `message.sender.username` when Telethon resolves a
  `User` entity. `NULL` when the sender has no public username or is not a
  user.
- `display_name` — a human-friendly display name for the sender. Composed
  from `first_name` + `last_name` (trimmed, joined with a single space) when
  either is present; otherwise the sender's `username`; otherwise `NULL`.

Both fields are populated on the fetch path from the `Message.sender` object
that Telethon already resolves on `get_messages`. No extra `get_entity`
round-trips are added.

The new fields are exposed automatically in the response payload of
`get_post`, `list_channel_posts`, `list_all_posts`, and the
`channel_digest` prompt because they all serialize via `asdict(post)`.

The sender fields are `NULL` for messages without a resolved `User` sender:
broadcast-channel posts (anonymous admin / channel-post), service messages
(`message.action is not None`), and deleted-account senders.

## Scope

In scope:

- `MessageInfo` and `Post` dataclasses (new optional fields).
- `posts` SQLite table — two new nullable columns + index on `display_name`.
- Schema migration via additive `ALTER TABLE`; existing rows stay `NULL`.
- Telethon fetch helpers — extract sender fields from already-resolved
  `Message.sender`.
- `db._row_to_post` and `db._SyncRepository.upsert_posts` — read and write the
  new fields.
- Server output — automatic via `asdict`; no tool signature changes.
- Tests for the model, the schema migration, the fetch path, and the
  payload shape.

Out of scope:

- Backfilling `username` / `display_name` for posts already in the cache.
  Consistent with the immutability rule (spec R26).
- Adding `index`-style MCP queries for "posts by user". The index is added
  so future queries can be added without a schema change.
- New MCP tools, new dependencies, new env vars.

## Risks

- **R1 — Telethon may not always resolve `Message.sender`.** For very old
  messages or messages from users the account has never interacted with,
  `sender` may be `None` while `sender_id` is set. We treat that case as
  `NULL` for both fields. If a future requirement needs the numeric id, a
  separate change can introduce `sender_id` and resolve via `get_entity`.
- **R2 — Schema migration runs on every startup.** The existing pattern
  (idempotent `ALTER TABLE` guarded by `PRAGMA table_info`) is reused.
  Failure paths are unchanged.
- **R3 — `display_name` composition is opinionated.** The
  `first + last / username / None` rule is documented as part of the spec.
  If project conventions later favor a different rule, treat it as a
  separate spec change.
- **R4 — Index on `display_name` adds write cost.** The index is added
  per the agreed plan; it will be used by future read paths but is unused
  by the current code. Acceptable trade-off; flagged here for future
  review.
- **R5 — JSON payload gains two keys.** Existing MCP clients ignore
  unknown keys (JSON convention), so no client breakage is expected.
