# Implementation Plan

## Approach

Use minimal direct extensions to the existing config, repository, and MCP server patterns. Do not add a service layer, dependency, public interface, model, or source module. Reuse existing domain exceptions and FastMCP exception mapping.

## Steps

1. **Configuration**
   - Add `backfill_days: int` to `AppConfig` in `src/package_tgmcpspy/config.py`.
   - Load `TGMCPSPY_BACKFILL_DAYS`, default `7`, through existing `_positive_int` validation.
   - Use it in `_update_channel` instead of the fixed seven-day value.

2. **Date modes for `list_channel_posts`**
   - Make `start_date`, `end_date`, and `days` optional parameters.
   - Add one private `server.py` helper that accepts exactly one complete mode:
     - both explicit dates; or
     - positive integer `days`.
   - Reject no mode, incomplete dates, mixed modes, booleans, zero, and negative days before repository or Telegram I/O.
   - Compute relative mode once as inclusive UTC `now - days` through `now`.
   - Preserve existing explicit-date parsing and leave `list_all_posts` unchanged.
   - Change `channel_digest_prompt` to call `list_channel_posts(..., days=days)`.

3. **`add_channel_batch`**
   - Add one private parser in `server.py` that splits `channels` on commas, trims values, ignores empty segments, deduplicates while preserving order, and rejects all-empty input.
   - Resolve and add identifiers sequentially using existing client/repository methods.
   - Check the resolved Telegram ID before upsert to report `already_tracked`.
   - Continue after expected `ChannelNotFoundError`, `TelegramError`, or `ConfigError`; return ordered per-item status/error and resolved channel metadata when available.
   - Do not fetch messages.

4. **Rename all-dialog tool**
   - Rename `sync_dialogs` to `add_channel_all` in `server.py`.
   - Preserve the existing behavior and `{"synced": ..., "channels": ...}` response exactly.
   - Do not retain an alias or fetch messages.

5. **Transactional full reset**
   - Add one private synchronous repository operation and matching async facade in `db.py`.
   - Within one `engine.begin()` transaction, count posts and channels, delete posts explicitly, then delete channels.
   - Return `posts_deleted` and `channels_deleted`; return zeros when empty.
   - Reuse this operation for both destructive tools so all current cache-owned metadata, posts, and update state are removed.

6. **Destructive tools**
   - Add `remove_all_channels(confirm: bool = False)` and `trash_all_messages(confirm: bool = False)`.
   - Require `confirm is True`; otherwise raise existing `ConfigError` before mutation.
   - Both tools call the same transactional reset and return its counts.

7. **Sequential execution**
   - Add one `asyncio.Lock` to existing `AppContext`, initialized in `app_lifespan`.
   - Acquire it at public mutating/Telegram-I/O tool boundaries: add/remove single, add batch/all, update single/all, and both reset tools.
   - Keep private helpers lock-free; aggregate tools acquire once to avoid nested-lock deadlocks.

8. **Documentation and OpenSpec tracking**
   - Update `README.md` tool examples and environment variables.
   - Remove public `sync_dialogs` references.
   - Mark implementation tasks complete only after their code and focused tests pass.

## Files

Change:

- `src/package_tgmcpspy/config.py`
- `src/package_tgmcpspy/server.py`
- `src/package_tgmcpspy/db.py`
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_db.py`
- `README.md`
- `openspec/changes/expand-channel-management-tools/tasks.md`

Keep unchanged unless implementation proves necessary:

- `src/package_tgmcpspy/models.py`
- `src/package_tgmcpspy/telegram.py`

## Tests

### `tests/test_config.py`

- Default backfill is 7.
- Positive configured backfill is loaded.
- Zero, negative, fractional, boolean-like, and nonnumeric values raise `ConfigError`.
- Update direct `AppConfig` construction.

### `tests/test_server.py`

- Explicit `list_channel_posts` range remains inclusive.
- Rolling days range is inclusive and uses one controlled UTC `now`.
- Reject absent, incomplete, mixed, zero, negative, and boolean modes before I/O.
- Digest prompt uses relative days mode.
- Batch parsing trims, ignores empties, preserves order, deduplicates, and rejects all-empty input.
- Batch processing is sequential, continues after expected failures, preserves result order, includes metadata, reports `already_tracked`, and never fetches messages.
- `add_channel_all` preserves the old response and does not fetch messages.
- MCP registration includes new tools and excludes `sync_dialogs`.
- Initial update uses configured backfill for each conversation kind; incremental update remains unchanged.
- Both destructive tools reject missing/false confirmation without repository calls.
- Both destructive tools return confirmed and idempotent zero-count results.
- Shared lock prevents updates and destructive resets from overlapping.
- Update app-context/config fixtures for `backfill_days` and the lock.

### `tests/test_db.py`

- Full reset deletes posts and channels and returns exact counts.
- Full reset on an empty database returns zero counts.
- An induced failure rolls back the entire reset transaction.

## Verification

1. Run each changed test module with `uv run pytest <target-file> -q --tb=short`.
2. Verify MCP registration/schema and destructive no-confirm behavior.
3. At explicit final verification, run `make check` once.
4. Report the intentional `sync_dialogs` API break and full-cache deletion behavior.
