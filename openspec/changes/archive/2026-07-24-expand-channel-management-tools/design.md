# Design: Expand channel-management tools and configurable backfill

## Overview

Implement the change as a small extension of the existing MCP, configuration, Telegram-resolution, and repository boundaries. No new dependency or project-level structural change is required.

## API design

### `list_channel_posts`

Retain the tool name and support exactly one query mode:

1. Explicit range: both `start_date` and `end_date` are supplied.
2. Relative range: `days` is supplied as a positive integer.

Relative mode computes an inclusive UTC interval from `now - days` through `now`. The tool raises an MCP error when no mode is supplied, only one explicit boundary is supplied, explicit boundaries and `days` are mixed, or `days` is not a positive integer. Explicit date parsing retains existing behavior.

Current time should be obtained at the server boundary and converted into the same UTC timestamp representation used by the repository. Tests should control this value without introducing wall-clock dependence.

### `add_channel_batch`

Accept one string parameter named `channels`.

Parsing is deterministic:

- Split on commas.
- Trim surrounding whitespace.
- Ignore empty segments.
- Deduplicate identifiers while preserving first-seen order.
- Raise an MCP error when no identifier remains.

Resolve and add identifiers sequentially. Continue after individual failures. Return one ordered result per deduplicated identifier with its identifier, resolved channel metadata when available, and either a success status or error message. An already tracked conversation is a non-error status such as `already_tracked`. The tool does not fetch messages.

### `add_channel_all`

Expose the existing all-dialog tracking operation only as `add_channel_all`. Preserve the former `sync_dialogs` behavior and response schema exactly. Do not retain a compatibility alias. Remove public documentation and prompt references to `sync_dialogs`.

### Destructive reset tools

Add `remove_all_channels(confirm: bool = False)` and `trash_all_messages(confirm: bool = False)`.

For both tools:

- Only literal `confirm=True` permits mutation.
- Missing or false confirmation raises an MCP error before database mutation.
- Delete all persisted local cache state, including conversations, tracking metadata, posts, update cursors, and other cache-owned records.
- Execute deletion and count collection in one database transaction.
- Return deletion counts, including at least conversations and posts; include additional cache-record counts if applicable.
- Succeed with zero counts when the cache is already empty.

Both names intentionally share the same full-reset semantics established by this change.

## Configuration and update behavior

Add `TGMCPSPY_BACKFILL_DAYS` to application configuration. It accepts positive integers only and defaults to 7. Invalid values fail through normal configuration validation.

When a conversation has no prior update state, `update_channel` uses this configured value for the initial UTC backfill cutoff for users, chats, and channels. Incremental-update behavior remains unchanged.

## Concurrency and transaction boundaries

All new tools participate in the same sequential tool-processing mechanism as update operations. Batch Telegram resolutions occur one at a time. Full-cache deletion is a single repository transaction, so callers observe either the complete reset or no reset.

## Data model

No new persistent entity is required. The configuration value is process configuration, not per-conversation state. Existing conversation and post records remain unchanged. Full reset removes all cache-owned rows; `trash_all_messages` does not preserve conversation metadata.

A typed deletion-count result should communicate the affected record counts without exposing database implementation details. Batch results should use the existing public channel metadata shape where possible and add an explicit per-item status/error representation.

## Error behavior

Validation errors and missing destructive confirmation are surfaced as MCP tool errors and cause no mutation. `add_channel_batch` treats per-identifier resolution/add failures as result entries rather than aborting the whole operation. Repository failure during full reset rolls back the entire transaction.

## Alternatives considered

- Keep `sync_dialogs` as an alias: rejected because complete replacement was requested.
- Accept a JSON list for batch add: rejected in favor of the requested comma-separated string.
- Make batch add atomic: rejected because partial progress and per-channel failures were requested.
- Preserve metadata in `trash_all_messages`: rejected; both destructive tools must clear all local cache state.
- Add per-tool locking: rejected in favor of the existing shared sequential-processing mechanism.
- Store backfill days per channel: rejected as out of scope.
