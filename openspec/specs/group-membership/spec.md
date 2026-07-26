# Spec: Local group membership

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines how tracked conversations carry local `groups` labels:
storage in a dedicated `channel_groups` table, management through
`set_channel_groups` and the optional `groups` argument on
`add_channel` / `add_channel_batch`, listing intersection, and clearing
on untrack. Groups are strictly local metadata and never change anything
on Telegram.

## Requirements

- **R1** Every cached conversation SHALL have a local `groups` membership stored in a `channel_groups` join table with `(channel_id, group_name)` rows.
- **R2** New and pre-existing rows SHALL default to an empty membership.
- **R3** Group memberships SHALL be local metadata and SHALL NOT change Telegram folders, channels, pins, memberships, or any server-side taxonomy.
- **R4** `list_tracked_channels` SHALL accept a `groups` argument and return only the tracked conversations whose `groups` field intersects the requested labels.
- **R5** The server SHALL provide `set_channel_groups(channel, groups)` plus the optional `groups` argument on `add_channel` and `add_channel_batch`. Each tool SHALL resolve only a locally cached tracked conversation, replace its group memberships atomically, return the serialized conversation, and perform no Telegram I/O.
- **R6** Updating groups for an absent or untracked conversation SHALL raise `ChannelNotFoundError`.
- **R7** Untracking a conversation SHALL delete its `channel_groups` rows in the same local database transaction.

## Scenarios

### S1 — Upgrade an existing database

```
GIVEN an existing database has no channel_groups table
WHEN the server initializes the schema
THEN it creates the channel_groups table with the agreed columns and index
  AND every existing conversation row has an empty groups list
  AND no manual migration is required
```

### S2 — New conversation starts with empty groups

```
WHEN a new conversation is added to the local cache
THEN its groups value is an empty list
```

### S3 — Re-upserting replaces groups

```
GIVEN tracked conversation A has groups ["news"]
WHEN A is upserted with refreshed title, username, or kind metadata
     and a new groups value ["tech", "urgent"]
THEN A's groups list is replaced by ["tech", "urgent"]
  AND the previous "news" membership is removed
```

### S4 — Assign groups on add

```
GIVEN conversation A is not tracked
WHEN add_channel("A", groups="tech news") is called
THEN A is persisted with tracked state and groups ["news", "tech"]
  AND the response contains the groups key
  AND Telegram state is unchanged
```

### S5 — Update groups through set_channel_groups

```
GIVEN tracked conversation A has groups ["tech"]
WHEN set_channel_groups("A", "urgent tech") is called
THEN A's groups list becomes ["tech", "urgent"]
  AND the response contains the groups key
  AND Telegram state is unchanged
```

### S6 — Clear groups through set_channel_groups

```
GIVEN tracked conversation A has groups ["tech"]
WHEN set_channel_groups("A", "") is called
THEN A's groups list becomes empty
  AND Telegram state is unchanged
```

### S7 — Reject groups update for an untracked conversation

```
GIVEN cached conversation A is not tracked
WHEN set_channel_groups("A", "tech") is called
THEN the tool raises ChannelNotFoundError as an MCP error
  AND A remains without group memberships
  AND Telegram is not contacted
```

### S8 — Untracking clears group memberships

```
GIVEN conversation A is tracked with groups ["tech", "urgent"]
WHEN remove_channel("A") succeeds
THEN A has is_tracked=false
  AND the channel_groups rows for A no longer exist
  AND the user's Telegram membership is unchanged
```