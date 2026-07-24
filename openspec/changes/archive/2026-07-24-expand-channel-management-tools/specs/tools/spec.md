# Tools delta specification

## ADDED Requirements

### Requirement: Batch channel addition

The server SHALL provide an MCP tool `add_channel_batch(channels)` that accepts comma-separated conversation identifiers. It SHALL trim surrounding whitespace, ignore empty segments, deduplicate identifiers while preserving first-seen order, and reject input from which no identifier remains.

The tool SHALL process identifiers sequentially, SHALL continue after individual failures, and SHALL NOT fetch messages. It SHALL return one result per deduplicated identifier in input order. Each result SHALL include the original normalized identifier, resolved conversation metadata when resolution succeeds, and either a success status or an error message. An already tracked conversation SHALL be reported with a non-error `already_tracked` status or equivalent.

#### Scenario: Parse and add a mixed batch

- **GIVEN** conversations A and B can be resolved
- **AND** A is already tracked
- **WHEN** `add_channel_batch` is called with `" A, ,B,A,"`
- **THEN** empty segments are ignored
- **AND** duplicate A is processed only once
- **AND** results are returned in the order A, B
- **AND** A is reported as already tracked
- **AND** B is added successfully
- **AND** no messages are fetched

#### Scenario: Continue after a failure

- **GIVEN** A and C can be resolved
- **AND** B cannot be resolved
- **WHEN** `add_channel_batch` is called with `"A,B,C"`
- **THEN** A, B, and C are processed sequentially
- **AND** B has an error result
- **AND** C is still processed
- **AND** results remain in input order

#### Scenario: Reject an empty batch

- **WHEN** `add_channel_batch` is called with an empty string or only commas and whitespace
- **THEN** the tool raises an MCP error
- **AND** no local tracking state changes

### Requirement: Remove all channels and local cache data

The server SHALL provide an MCP tool `remove_all_channels(confirm)` that permanently removes every locally persisted conversation, tracking record, post, update cursor, and other cache-owned record. The operation SHALL be transactional and SHALL return deletion counts, including conversation and post counts.

The tool SHALL require `confirm=True`. Missing or false confirmation SHALL raise an MCP error before mutation. Calling the tool on an empty database SHALL succeed and return zero counts. The tool SHALL NOT leave, unsubscribe from, or otherwise modify Telegram conversations.

#### Scenario: Confirmed full removal

- **GIVEN** the local cache contains conversations, posts, and update state
- **WHEN** `remove_all_channels(confirm=True)` is called
- **THEN** all cache-owned data is permanently deleted in one transaction
- **AND** deletion counts are returned
- **AND** Telegram memberships and subscriptions are unchanged

#### Scenario: Reject removal without confirmation

- **GIVEN** the local cache contains data
- **WHEN** `remove_all_channels` is called without `confirm=True`
- **THEN** the tool raises an MCP error
- **AND** no local data changes

#### Scenario: Remove from an empty cache

- **GIVEN** the local cache is empty
- **WHEN** `remove_all_channels(confirm=True)` is called
- **THEN** the call succeeds
- **AND** all deletion counts are zero

### Requirement: Trash all local cache data

The server SHALL provide an MCP tool `trash_all_messages(confirm)` with the same transactional full-reset behavior as `remove_all_channels`. Despite its name, it SHALL remove every locally persisted conversation, metadata record, post, update cursor, and other cache-owned record. It SHALL return deletion counts and SHALL require `confirm=True`.

After a confirmed reset, a later channel addition and first update SHALL use the configured initial backfill because no update state remains.

#### Scenario: Confirmed trash resets update state

- **GIVEN** the local cache contains conversations, posts, and update cursors
- **WHEN** `trash_all_messages(confirm=True)` is called
- **THEN** all cache-owned data is permanently deleted in one transaction
- **AND** deletion counts are returned
- **AND** a subsequently re-added conversation has no prior update state

#### Scenario: Reject trash without confirmation

- **GIVEN** the local cache contains data
- **WHEN** `trash_all_messages` is called without `confirm=True`
- **THEN** the tool raises an MCP error
- **AND** no local data changes

#### Scenario: Trash an empty cache

- **GIVEN** the local cache is empty
- **WHEN** `trash_all_messages(confirm=True)` is called
- **THEN** the call succeeds
- **AND** all deletion counts are zero

### Requirement: Configurable initial backfill period

The server SHALL read optional environment variable `TGMCPSPY_BACKFILL_DAYS`. It SHALL accept positive integers only and SHALL default to 7 when absent. Invalid values SHALL fail configuration validation.

For a conversation without prior update state, the server SHALL fetch messages from the inclusive UTC interval beginning the configured number of days before the update time. This behavior SHALL apply uniformly to user, chat, and channel conversation kinds. Incremental updates SHALL remain based on existing update state.

#### Scenario: Use configured initial backfill

- **GIVEN** `TGMCPSPY_BACKFILL_DAYS=14`
- **AND** a tracked conversation has no prior update state
- **WHEN** that conversation is updated
- **THEN** messages from the inclusive previous 14-day UTC interval are eligible for fetching

#### Scenario: Use default initial backfill

- **GIVEN** `TGMCPSPY_BACKFILL_DAYS` is absent
- **AND** a tracked conversation has no prior update state
- **WHEN** that conversation is updated
- **THEN** messages from the inclusive previous 7-day UTC interval are eligible for fetching

#### Scenario: Reject invalid backfill configuration

- **WHEN** `TGMCPSPY_BACKFILL_DAYS` is zero, negative, fractional, boolean-like, or non-numeric
- **THEN** configuration validation fails

### Requirement: Shared sequential execution

All tools added by this change SHALL use the same sequential-processing mechanism as existing update tools. Destructive operations SHALL not overlap update operations, and `add_channel_batch` SHALL resolve and add conversations one at a time.

#### Scenario: Reset and update are serialized

- **GIVEN** one client requests a channel update
- **AND** another client requests a confirmed full reset concurrently
- **WHEN** the server processes both calls
- **THEN** one operation completes before the other begins
- **AND** they do not mutate the cache concurrently

## MODIFIED Requirements

### Requirement: List channel posts by one date-selection mode

The server SHALL retain the MCP tool name `list_channel_posts`. A caller SHALL select exactly one of these modes:

- Explicit mode: provide both `start_date` and `end_date`.
- Relative mode: provide `days` as a positive integer.

Relative mode SHALL query the inclusive UTC interval from `now - days` through `now`. Explicit mode SHALL retain the existing inclusive UTC date parsing and range behavior.

The tool SHALL raise an MCP error when no mode is supplied, when only one explicit date boundary is supplied, when explicit boundaries and `days` are supplied together, or when `days` is not a positive integer. Validation failure SHALL not query or mutate cached data.

#### Scenario: List posts using rolling days

- **GIVEN** the current time is `2026-07-23T12:00:00Z`
- **AND** the conversation has posts exactly at `2026-07-20T12:00:00Z`, inside the interval, and after the current time
- **WHEN** `list_channel_posts` is called with `days=3`
- **THEN** posts from the inclusive interval `2026-07-20T12:00:00Z` through `2026-07-23T12:00:00Z` are returned
- **AND** posts outside that interval are excluded

#### Scenario: Retain explicit range mode

- **WHEN** `list_channel_posts` is called with valid `start_date` and `end_date` and no `days`
- **THEN** it returns posts using the existing inclusive UTC range behavior

#### Scenario: Reject absent selection mode

- **WHEN** `list_channel_posts` is called without dates or `days`
- **THEN** the tool raises an MCP error

#### Scenario: Reject incomplete explicit range

- **WHEN** `list_channel_posts` is called with only `start_date` or only `end_date`
- **THEN** the tool raises an MCP error

#### Scenario: Reject mixed selection modes

- **WHEN** `list_channel_posts` is called with `days` and either explicit date boundary
- **THEN** the tool raises an MCP error

#### Scenario: Reject invalid relative days

- **WHEN** `list_channel_posts` is called with zero, negative, fractional, boolean, or non-numeric `days`
- **THEN** the tool raises an MCP error

### Requirement: Add every Telegram dialog under the new tool name

The server SHALL provide `add_channel_all` as the sole MCP tool for fetching every accessible Telegram dialog and marking each conversation as tracked. It SHALL preserve the behavior and response schema formerly exposed by `sync_dialogs` and SHALL NOT fetch messages.

Public documentation and prompts SHALL refer only to `add_channel_all`.

#### Scenario: Add all dialogs

- **GIVEN** the Telegram user has accessible user, chat, and channel dialogs
- **WHEN** the MCP client calls `add_channel_all`
- **THEN** every dialog is marked as tracked using the former `sync_dialogs` behavior
- **AND** the response uses the former response schema
- **AND** no messages are fetched

## REMOVED Requirements

### Requirement: Legacy `sync_dialogs` MCP tool name

The MCP tool `sync_dialogs` SHALL no longer be exposed, documented, or referenced by public prompts. No compatibility alias SHALL remain.

#### Scenario: Legacy name is unavailable

- **WHEN** an MCP client enumerates available tools
- **THEN** `sync_dialogs` is absent
- **AND** `add_channel_all` is present
