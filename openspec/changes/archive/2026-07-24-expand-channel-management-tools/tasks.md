# Tasks

- [x] Add delta-driven tests for `list_channel_posts` explicit and rolling-day modes, inclusive boundaries, and every invalid parameter combination.
- [x] Add `TGMCPSPY_BACKFILL_DAYS` configuration parsing, positive-integer validation, and default-7 tests.
- [x] Use configured backfill days for first updates across user, chat, and channel conversation kinds; retain incremental-update behavior.
- [x] Add parsing tests for comma-separated batch input: trimming, empty-segment removal, stable deduplication, and all-empty rejection.
- [x] Implement `add_channel_batch` with sequential processing, continued partial failures, stable ordered results, resolved metadata, and `already_tracked` status.
- [x] Rename the public `sync_dialogs` tool to `add_channel_all` without retaining an alias, preserving behavior and response schema.
- [x] Add repository support for transactional full-cache deletion with pre-deletion counts and rollback on failure.
- [x] Implement confirmed, idempotent `remove_all_channels` and `trash_all_messages` tools using the same full-reset operation.
- [x] Ensure the new tools and destructive operations use the existing shared sequential-processing mechanism.
- [x] Update public documentation and prompts for the new APIs, configuration variable, and removal of `sync_dialogs`.
- [x] Run focused test modules after each behavior slice.
- [x] At explicit final verification, run `make check` and summarize any remaining compatibility or data-loss risks.
