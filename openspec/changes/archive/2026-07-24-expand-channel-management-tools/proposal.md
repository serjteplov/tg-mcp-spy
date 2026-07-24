# Proposal: Expand channel-management tools and configurable backfill

## Why

The MCP API currently supports only explicit date ranges for per-channel post queries, individual channel tracking changes, a fixed seven-day initial backfill, and the legacy `sync_dialogs` name. Operators need relative-date queries, bulk channel management, explicit local-cache reset operations, and configurable initial history depth.

## What changes

- Extend `list_channel_posts` with an inclusive rolling UTC `days` mode while retaining explicit `start_date` and `end_date` mode.
- Add `add_channel_batch(channels)` for sequentially adding comma-separated identifiers with per-channel results.
- Replace `sync_dialogs` with `add_channel_all`, preserving behavior and response shape.
- Add confirmed, transactional `remove_all_channels` and `trash_all_messages` tools that permanently clear all persisted local cache data and return deletion counts.
- Add `TGMCPSPY_BACKFILL_DAYS`, a positive-integer configuration setting with a default of 7.
- Keep all new operations serialized with existing update operations.
- Update public documentation and prompts to remove `sync_dialogs` references.

## Scope

### In scope

- MCP schemas, validation, responses, and errors for the changed and new tools.
- Local database operations needed for atomic full-cache deletion and count reporting.
- Application configuration for the initial backfill period.
- Deterministic tests and public documentation updates.

### Non-goals

- Deleting messages from Telegram.
- Leaving or unsubscribing from Telegram conversations.
- Fetching messages automatically from `add_channel_batch` or `add_channel_all`.
- Per-channel backfill overrides.
- Adding a `days` mode to `list_all_posts`.
- Database backup or restoration before destructive operations.

## Risks

- Removing `sync_dialogs` is an intentional breaking API change for existing MCP clients.
- Full-cache deletion is destructive; strict confirmation and transaction boundaries are required.
- `remove_all_channels` and `trash_all_messages` intentionally have identical full-reset semantics, which may surprise clients based on their names.
- Relative-date tests require a controlled current time to remain deterministic.
- Bulk resolution may encounter partial Telegram failures and must preserve stable input ordering while continuing sequentially.
