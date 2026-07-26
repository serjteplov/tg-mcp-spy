# Spec: Tracked conversations

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the MCP tool surface for adding, listing, syncing, and
removing tracked Telegram conversations, and the batch-add helper. Per-kind
semantics live in the `conversation-kinds` spec; cache resets live in the
`cache-reset` spec; reading cached posts lives in the `post-queries` spec.

## Requirements

- **R1** The server SHALL provide an MCP tool `add_channel_all` that fetches every conversation in the user's Telegram dialog list and marks it as tracked in the local cache.
- **R2** The server SHALL provide an MCP tool `list_tracked_channels` returning all locally tracked conversations and their kinds.
- **R3** The server SHALL provide MCP tools `add_channel(channel)` and `remove_channel(channel)` that update only the local tracked flag, not the user's Telegram subscriptions or memberships.
- **R4** The server SHALL provide an MCP tool `update_channel(channel)` that fetches posts for any tracked conversation.
- **R5** The server SHALL provide an MCP tool `update_all_channels` that updates every tracked conversation sequentially.
- **R6** The server SHALL provide an MCP tool `add_channel_batch(channels)` that accepts comma-separated conversation identifiers, trims whitespace, ignores empty segments, deduplicates identifiers while preserving first-seen order, and rejects input with no remaining identifier.
- **R7** `add_channel_batch` SHALL process identifiers sequentially, continue after individual resolution or add failures, return one ordered result per deduplicated identifier with normalized identifier and resolved metadata when available, report success or error status, report already tracked conversations without error, and never fetch messages.
- **R8** The MCP tool `add_channel_all` SHALL be the sole all-dialog tracking tool; the legacy `sync_dialogs` name SHALL not be exposed, documented, or referenced by public prompts.

## Scenarios

### Tracking operations

#### S1 — Sync dialogs from Telegram

```
GIVEN the server is configured with a valid Telegram user session
  AND the user is subscribed to broadcast channels A and B
WHEN the MCP client calls add_channel_all
THEN the response indicates success
  AND both A and B are marked as tracked in the local cache
```

#### S2 — List tracked channels

```
GIVEN channels A and B are tracked
  AND channel C is not tracked
WHEN the MCP client calls list_tracked_channels
THEN the response contains A and B
  AND the response does not contain C
```

#### S3 — Remove channel locally

```
GIVEN channel A is tracked
WHEN the MCP client calls remove_channel("A")
THEN channel A is no longer tracked
  AND the user's Telegram subscription to A is unchanged
```

#### S4 — Add channel locally

```
GIVEN channel D exists on Telegram but is not tracked
WHEN the MCP client calls add_channel("D")
THEN channel D becomes tracked
  AND the user's Telegram subscription to D is unchanged
```

#### S5 — Update all channels

```
GIVEN channels A and B are tracked
  AND both have new posts since their last update
WHEN the MCP client calls update_all_channels
THEN A and B are updated sequentially
  AND the response contains per-channel fetched counts
```

### Batch add

#### S6 — Batch add parses and processes ordered identifiers

```
GIVEN conversations A and B can be resolved
  AND A is already tracked
WHEN the MCP client calls add_channel_batch(" A, ,B,A,")
THEN empty segments are ignored
  AND duplicate A is processed only once
  AND results are returned in the order A, B
  AND A is reported as already tracked
  AND B is added successfully
  AND no messages are fetched
```

#### S7 — Batch add continues after a failure

```
GIVEN A and C can be resolved
  AND B cannot be resolved
WHEN the MCP client calls add_channel_batch("A,B,C")
THEN A, B, and C are processed sequentially
  AND B has an error result
  AND C is still processed
  AND results remain in input order
```

#### S8 — Empty batch is rejected

```
WHEN the MCP client calls add_channel_batch with an empty string or only commas and whitespace
THEN the tool raises an MCP error
  AND no local tracking state changes
```

### Backward compatibility

#### S9 — Legacy all-dialog tool name is unavailable

```
WHEN an MCP client enumerates available tools
THEN add_channel_all is present
  AND sync_dialogs is absent
```