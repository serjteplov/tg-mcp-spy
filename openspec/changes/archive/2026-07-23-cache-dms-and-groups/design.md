# Design: Cache direct messages, groups, and channels

## Overview

Generalize the conversation entity from `Channel` to a discriminated union (`channel | chat | user`). Keep the dataclass named `Channel` for now to minimize churn on the public shape; just add a `kind` field. Relax the Telethon wrapper to accept all three Telethon entity types. Migrate the SQLite schema by adding a `kind` column with a default of `'channel'` so existing rows keep working.

## Module layout

```
src/package_tgmcpspy/
  models.py        # add ConversationKind literal + kind field on ChannelInfo/Channel
  db.py            # add kind column to channels_table; read/write through _row_to_channel
  telegram.py      # broaden resolve_identifier, get_dialogs, _resolve_entity to three peer types
  server.py        # server context/launch hardening (see "Server context and launch" below)
  config.py        # no changes

tests/
  conftest.py      # extend FakeTelegramClient to return Chat/User entities
  test_telegram.py # broaden resolve_identifier tests to cover all three entity types
  test_db.py       # assert pre-existing rows read back with kind="channel"
  test_server.py   # cover sync_dialogs and add_channel for non-channel entities
```

## Configuration

No new env vars. `TGMCPSPY_POST_TTL_DAYS` continues to apply uniformly to all kinds.

## Data model

### `channels` (modified)

Add column:
- `kind` — `String`, `nullable=False`, `default="channel"`. Values: `'channel'`, `'chat'`, `'user'`.

Existing rows get `'channel'` when the schema is re-applied via `metadata.create_all` because the column declares a default; SQLAlchemy will add the column to the table on next start without a separate migration step.

### `posts`

No changes.

### Domain types

`ChannelInfo` and `Channel` gain a `kind: ConversationKind` field:

```python
type ConversationKind = Literal["channel", "chat", "user"]
```

`Channel.username` stays nullable. For `User`, `title` becomes `"{first_name} {last_name}".strip()` (or just `first_name` when `last_name` is empty); `username` is the bare Telegram username (no leading `@`, matching the Channel convention so callers can use a plain identifier for both kinds) and NULL when the user is private. For `Chat`, `title` is the chat title and `username` is NULL.

The class name `Channel` and the exception name `ChannelNotFoundError` stay the same — the spec language refers to "conversations" or "tracked items", but the Python symbols do not change.

## Concurrency

No changes. All MCP tool calls remain sequential.

## Data retention

No changes. The TTL purge applies uniformly to all kinds.

## Event payloads and notifications

No changes. Server remains purely request/response.

## Private content

Now includes direct messages and group messages. Same host-side mitigations apply: env-only credentials, no log text, local bind.

## Telegram client wrapper

### `get_dialogs`

Drop the `entity.broadcast` filter. Iterate every dialog and convert any of `Channel`, `Chat`, `User` to a `ChannelInfo` with the right `kind`. Mapping:

- `Channel.broadcast` or `Channel.megagroup` → `kind='channel'`.
- `Chat` (legacy small group) → `kind='chat'`.
- `User` → `kind='user'`.

### `resolve_identifier(identifier)`

Let Telethon discriminate:

- String → `client.get_entity(string)` (works for `@username` of any entity, full name, phone number).
- Numeric → `client.get_entity(int_or_str)` (Telethon tries `PeerUser`, `PeerChat`, then `PeerChannel` based on what the user can access).

The wrapper then checks `isinstance(entity, (Channel, Chat, User))`. If none of those, raise `ChannelNotFoundError` with a clearer message that mentions "conversation" instead of "channel".

### `_resolve_entity(info)`

Dispatch by `info.kind`:

- `'channel'` → `PeerChannel(info.telegram_id)`.
- `'chat'` → `PeerChat(info.telegram_id)`.
- `'user'` → `PeerUser(info.telegram_id)`.

### `_entity_to_channel_info(entity)`

Replace the static helper with a dispatcher that produces the right `kind` and a sensible `title` per entity type.

## Syncing and updating

### `sync_dialogs`

No changes to the orchestrator in `server.py`. Because `get_dialogs` now returns all kinds, `sync_dialogs` automatically mirrors DMs and groups.

### `update_channel(channel)`

No changes. The 7-day backfill and incremental-after-`last_message_id` logic apply uniformly.

### `update_all_channels`

No changes. Iterates every tracked conversation (channel, chat, or user) and updates each.

## MCP surface

No tool renames. Documentation strings on each tool note that "channel" means any tracked conversation; a small note is also added to the README.

## Date handling

No changes.

## Lifespan

No changes.

## Error handling

`resolve_identifier` raises `ChannelNotFoundError` for anything that does not resolve to one of `Channel`, `Chat`, `User`. The exception class name stays the same to avoid import churn; only the message text mentions "conversation".

## Logging and leak prevention

- No new logging. Post text and DM content are never logged.
- Same env-only credential policy.

## Server context and launch

While implementing the change we found that ``ctx.request_context.lifespan_context``
is broken on mcp 1.28.x: FastMCP swallows the underlying ``LookupError`` inside
``get_context()`` and hands tools a ``Context`` whose ``_request_context`` is
``None``. Every tool that called ``ctx.request_context.lifespan_context``
crashed with "Context is not available outside of a request" on both the SSE
and stdio paths. To unblock the broader cache-DMs/groups rollout (and to make
``make check`` pass), this change adopts a small module-level workaround in
``server.py``:

- A module global ``_app_context`` is bound by ``app_lifespan`` to the live
  ``AppContext``. Tools call ``_context(ctx)`` (which intentionally ignores
  ``ctx``) to fetch it. The docstring records the rationale so the workaround
  can be revisited when the upstream bug is fixed.
- ``main()`` configures ``logging.basicConfig`` so lifespan and tool errors are
  visible in the console, and switches ``uvicorn.run`` to the direct
  ``mcp.sse_app()`` reference. ``reload=True`` is dropped because reload
  requires a string import path; this is a deliberate developer-experience
  trade-off, not an oversight.

No public MCP contract changes. Tool signatures, return shapes, and the JSON
wire format are unchanged.

## Testing

- New `test_telegram.py` cases: `resolve_identifier` for a `User` entity, for a legacy `Chat` entity, for a `Channel` supergroup (broadcast=False, megagroup=True), and a numeric id that resolves to a user.
- New `test_db.py` case: pre-existing rows read back with `kind='channel'` after schema migration.
- New `test_server.py` cases: `add_channel` with a user id, `sync_dialogs` picking up DMs and groups, `update_all_channels` updating all kinds.
- Existing tests continue to pass — default `kind='channel'` matches prior behavior.

## Tooling changes

- None. No new dependencies.

## Risks

- A user id and a channel id share the numeric namespace. The wrapper now relies on Telethon's `get_entity` to return the right type. If a numeric id is ambiguous (unlikely but possible during migration), the resolver prefers whatever Telethon returns first.
- README must be updated to say "conversations" rather than "channels" wherever the broader scope matters.
- `sync_dialogs` may now add many items users do not actually want tracked. Document the `remove_channel` escape hatch in the README.