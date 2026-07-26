# Spec: Conversation kinds

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines how the `tg-mcp-spy` MCP server distinguishes Telegram
`User`, legacy `Chat`, and broadcast/supergroup `Channel` entities through
the `kind` discriminator, and how identifiers and initial backfill are
interpreted across kinds.

## Requirements

- **R1** Every cached conversation SHALL carry a `kind` field with value `channel`, `chat`, or `user`.
- **R2** The server SHALL persist the conversation kind in a dedicated SQLite column with default value `channel` so existing rows remain valid without a manual migration step.
- **R3** `add_channel_all` SHALL mirror every conversation in the user's Telegram dialog list (DMs, legacy chats, and channels), not only broadcast channels.
- **R4** `add_channel(channel)` SHALL accept identifiers that resolve to a `User`, `Chat`, or `Channel` entity on Telegram.
- **R5** Tools SHALL accept identifiers that Telethon resolves to a `User`, `Chat`, or `Channel`, including Telegram usernames and numeric ids (positive user ids, negative legacy-chat ids, and `-100...` channel or supergroup ids).
- **R6** `update_channel` and `update_all_channels` SHALL fetch and cache posts from any tracked `User`, `Chat`, or `Channel`.
- **R7** First-add backfill SHALL use the configured number of previous days uniformly for `user`, `chat`, and `channel` conversations.
- **R8** The server SHALL read optional `TGMCPSPY_BACKFILL_DAYS`, accepting positive integers only and defaulting to 7. Invalid values SHALL fail configuration validation.

## Scenarios

### S1 — Sync dialogs includes DMs and groups

```
GIVEN the server is configured with a valid Telegram user session
  AND the user has a direct message dialog with user U
  AND a legacy small-group chat dialog C
  AND a broadcast-channel dialog B
WHEN the MCP client calls add_channel_all
THEN the response includes U, C, and B
  AND U is marked with kind="user"
  AND C is marked with kind="chat"
  AND B is marked with kind="channel"
```

### S2 — Add user by numeric id

```
GIVEN the user has access to user U with Telegram id 6199205118
WHEN the MCP client calls add_channel("6199205118")
THEN U is added to the tracked list with kind="user"
  AND the user's Telegram subscription is unchanged
```

### S3 — Add legacy chat by id

```
GIVEN the user is a member of legacy chat C with a negative id
WHEN the MCP client calls add_channel("-123456789")
THEN C is added to the tracked list with kind="chat"
```

### S4 — Add supergroup by id

```
GIVEN the user is a member of supergroup S with id -1001234567890
WHEN the MCP client calls add_channel("-1001234567890")
THEN S is added to the tracked list with kind="channel"
```

### S5 — Existing rows default to kind="channel"

```
GIVEN the SQLite database contains rows inserted before this change
WHEN the server starts
THEN those rows are read successfully with kind="channel"
  AND the server can resolve, update, and list them as before
```

### S6 — First-add backfill uses configured days for every kind

```
GIVEN U (a user DM) has never been updated
  AND TGMCPSPY_BACKFILL_DAYS is set to 14
  AND U has 2 messages within the last 14 days and 1 older message
WHEN the MCP client calls update_channel("U")
THEN exactly those 2 recent messages are cached
```

### S7 — Configured initial backfill

```
GIVEN TGMCPSPY_BACKFILL_DAYS=14
  AND a tracked conversation has no prior update state
WHEN that conversation is updated
THEN messages from the inclusive previous 14-day UTC interval are eligible for fetching
```

### S8 — Invalid backfill configuration is rejected

```
WHEN TGMCPSPY_BACKFILL_DAYS is zero, negative, fractional, boolean-like, or non-numeric
THEN configuration validation fails
```