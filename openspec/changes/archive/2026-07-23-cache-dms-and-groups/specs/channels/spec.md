# Delta spec: Cache direct messages, groups, and channels

## Status

APPROVED — implemented, reviewed, and verified.

## Scope

This delta extends `openspec/specs/channels/spec.md` to support direct messages with users, legacy small-group chats, and channels (public/private broadcast plus supergroups) through the same MCP tool surface. Tool names are unchanged.

## Requirements

### ADDED

- **R27** Every cached conversation SHALL carry a `kind` field with value `channel`, `chat`, or `user`.
- **R28** `sync_dialogs` SHALL mirror every conversation in the user's Telegram dialog list (DMs, legacy chats, and channels), not only broadcast channels.
- **R29** `add_channel(channel)` SHALL accept identifiers that resolve to a `User`, `Chat`, or `Channel` entity on Telegram.
- **R30** `update_channel` and `update_all_channels` SHALL fetch and cache posts from any tracked `User`, `Chat`, or `Channel`.
- **R31** The server SHALL persist the conversation kind in a dedicated SQLite column with default value `channel` so existing rows remain valid without a manual migration step.
- **R32** First-add backfill SHALL remain at 7 days for every kind.

### MODIFIED

- **M3** `TelegramClientWrapper.resolve_identifier` SHALL accept entities of type `User`, `Chat`, or `Channel` (previously only `Channel`).
- **M4** `TelegramClientWrapper.get_dialogs` SHALL return all dialog kinds, not only broadcast channels.
- **M5** Tool descriptions SHALL refer to "conversations" or "tracked items" alongside "channels" to reflect the broader scope; tool names remain unchanged.

### REMOVED

- None.

## Scenarios

### Broadened sync

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

### Resolution beyond channels

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

- The dataclass stays named `Channel` to minimize churn; "channel" in the public API is now a synonym for "tracked conversation".
- `_resolve_entity` dispatches by `kind` to `PeerUser`, `PeerChat`, or `PeerChannel`.
- The `kind` column has a SQLAlchemy default of `'channel'` so existing databases continue to load without a manual migration.
- The parent spec is `openspec/specs/channels/spec.md`. This delta will be merged into it during archive.