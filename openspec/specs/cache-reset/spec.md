# Spec: Local cache reset

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the destructive MCP tools that clear the local SQLite
cache: `remove_all_channels` and `trash_all_messages`. Both require
explicit confirmation, run in a single transaction, and never touch
Telegram memberships or subscriptions.

## Requirements

- **R1** The server SHALL provide `remove_all_channels(confirm)` that, when called with `confirm=True`, transactionally deletes every cache-owned conversation, tracking record, post, update cursor, and other persisted cache record, without changing Telegram memberships or subscriptions, and returns deletion counts including conversations and posts.
- **R2** `remove_all_channels` SHALL reject missing or false confirmation before mutation and SHALL succeed with zero counts on an empty cache.
- **R3** The server SHALL provide `trash_all_messages(confirm)` with the same confirmed, transactional full-cache reset semantics, deletion counts, and confirmation requirement as `remove_all_channels`; after reset, a later re-add and first update SHALL use configured initial backfill.

## Scenarios

### S1 — Confirmed full removal

```
GIVEN the local cache contains conversations, posts, and update state
WHEN the MCP client calls remove_all_channels(confirm=True)
THEN all cache-owned data is permanently deleted in one transaction
  AND deletion counts are returned
  AND Telegram memberships and subscriptions are unchanged
```

### S2 — Removal without confirmation is rejected

```
GIVEN the local cache contains data
WHEN the MCP client calls remove_all_channels without confirm=True
THEN the tool raises an MCP error
  AND no local data changes
```

### S3 — Removal from an empty cache

```
GIVEN the local cache is empty
WHEN the MCP client calls remove_all_channels(confirm=True)
THEN the call succeeds
  AND all deletion counts are zero
```

### S4 — Confirmed trash resets update state

```
GIVEN the local cache contains conversations, posts, and update cursors
WHEN the MCP client calls trash_all_messages(confirm=True)
THEN all cache-owned data is permanently deleted in one transaction
  AND deletion counts are returned
  AND a subsequently re-added conversation has no prior update state
```

### S5 — Trash without confirmation is rejected

```
GIVEN the local cache contains data
WHEN the MCP client calls trash_all_messages without confirm=True
THEN the tool raises an MCP error
  AND no local data changes
```

### S6 — Trash from an empty cache

```
GIVEN the local cache is empty
WHEN the MCP client calls trash_all_messages(confirm=True)
THEN the call succeeds
  AND all deletion counts are zero
```