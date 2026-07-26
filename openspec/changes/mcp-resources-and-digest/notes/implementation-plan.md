# Implementation plan

Approved option: **A — additive helpers in the existing modules**.

Rationale: matches the user constraint ("prefer existing patterns over new
abstraction layers") and the spec's "no new dependency" requirement. No new
module, no new public service interface, no new dependency. All new symbols
are private helpers inside `server.py` and `db.py`, all new MCP surfaces
extend existing patterns.

## Constraints applied

- **Zero-new-module.** All edits land in `models.py`, `db.py`, `server.py`,
  `tests/test_db.py`, `tests/test_server.py`, `README.md`.
- **Reuse existing exception mapping.** `ChannelNotFoundError`, `ConfigError`,
  `TelegramError` are the only domain exceptions. Resources, Completion, and
  the digest prompt raise them directly; FastMCP converts them to MCP error
  responses. No new exception types.
- **No new public service interface.** Private helpers stay underscore-prefixed
  and follow the existing `_context`, `_channel_to_dict`, `_resolve_db_channel`
  shape.
- **Reuse existing helpers.** `_context`, `_channel_to_dict`, `_post_to_dict`,
  `_parse_utc_datetime`, `_parse_date_range`, `_resolve_post_range`,
  `_parse_batch_identifiers`, `normalize_identifier`, `init_schema`,
  `_upgrade_schema`, `Repository.upsert_channel` / `set_tracked` /
  `list_tracked_channels` / `get_post` / `list_channel_posts` are all extended
  in place.

## Phases

### Phase 1 — Model & schema

- `models.py`: add `groups: tuple[str, ...] = ()` to the frozen `Channel`
  dataclass as a kwarg with default.
- `db.py`: declare `channel_groups_table` with `(channel_id, group_name)` PK
  and `ON DELETE CASCADE` FK; add the table to `metadata` so
  `metadata.create_all` creates it on fresh databases.
- `db.py`: extend `_upgrade_schema` with a parallel `CREATE TABLE IF NOT
  EXISTS channel_groups` block guarded by `sqlite_master` so existing
  databases receive the table on startup.
- `db.py`: add `_normalize_groups(value: str) -> tuple[str, ...]` at module
  scope (strip, split on whitespace, drop empties, dedup, sort).
- `db.py`: update `_row_to_channel` to join `channel_groups` and populate
  `groups` as a sorted tuple. Add a `_get_channel_groups(conn, channel_id)`
  helper used by every read path.
- `db.py`: update `upsert_channel(info, *, is_tracked=True, groups="")` to
  replace groups atomically through a new `_replace_channel_groups(conn,
  channel_id, groups_tuple)` inside the same transaction.
- `db.py`: update `set_tracked(telegram_id, tracked)` to delete
  `channel_groups` rows for the channel when `tracked=False`, in the same
  transaction.
- `db.py`: add `Repository.set_channel_groups(telegram_id, groups)` async
  façade (returns the refreshed `Channel` or `None`).
- `db.py`: add `Repository.list_tracked_channels(groups=None)` async façade
  with optional intersection filter.
- `db.py`: add `Repository.list_recent_cached_post_ids(channel_id, limit=100)`
  sync + async for dependent Completion.

Tests: `tests/test_db.py` — fresh schema, upgraded schema, normalization,
replace-on-upsert, untrack-clearing, list-with-filter, newest-100 ordering.

### Phase 2 — Server tools

- `server.py`: add `_get_app_context() -> AppContext` (no-arg sibling of
  `_context`); resource and prompt handlers use it.
- `server.py`: add `_resolve_local_channel(app, identifier) -> Channel` using
  `normalize_identifier` and the existing `repo.get_channel_by_*` lookups;
  raise `ChannelNotFoundError` on miss. Never call `app.client`.
- `server.py`: add `_canonical_identifier(channel) -> str` returning
  `channel.username` else `str(channel.telegram_id)`.
- `server.py`: extend `add_channel` and `add_channel_batch` with optional
  `groups: str = ""`; pass to `repo.upsert_channel`.
- `server.py`: add `@mcp.tool() set_channel_groups(ctx, channel, groups)`:
  resolve via `_resolve_db_channel`, call `app.repo.set_channel_groups`,
  return `_channel_to_dict`.

Tests: `tests/test_server.py` — `add_channel` and `add_channel_batch` persist
groups; `set_channel_groups` succeeds, rejects untracked.

### Phase 3 — Live resources

- `server.py`: add four private read helpers
  (`_list_tracked_channels_resource`, `_get_post_for_resource`,
  `_list_posts_for_resource`) that all use `_resolve_local_channel` and the
  existing repo methods.
- `server.py`: replace the two placeholder resources with live async handlers
  declaring `mime_type="application/json"`. Add the two new templates
  `posts://{channel}/recent/{days}` and
  `posts://{channel}/range/{start_date}/{end_date}` with the same MIME type.
  Reuse `_parse_date_range` and `_resolve_post_range` validation; raise
  `ConfigError` and `ChannelNotFoundError` directly.

Tests: `tests/test_server.py` — JSON shape, MIME type, ordering, date modes,
invalid input, missing channel/post, no-Telegram assertion (patch
`fake_client.resolve_identifier` to raise if called).

### Phase 4 — Completion

- `server.py`: add `_channel_completion_values(app, prefix)` and
  `_post_id_completion_values(app, channel_identifier, prefix)`.
- `server.py`: add `_parse_digest_space_list(value)` returning
  `(prior_segments, active_segment)` and a sibling `_format_digest_channels`
  for the prompt builder.
- `server.py`: register a single `@mcp.completion()` handler that dispatches
  on `argument.name`: `channel` / `channels` → channel completion;
  `post_id` → dependent completion using `context.arguments.get("channel")`
  (empty list when context missing or channel unknown); everything else
  returns `Completion(values=[])`. Use `mcp.types.Completion` for the
  return type.

Tests: `tests/test_server.py` — channel prefix / dedup / cap 100; post-ID
dependency on missing context; unknown channel; newest 100 descending;
space-aware digest channels exclude already-typed values; no completion for
`days` / `start_date` / `end_date`.

### Phase 5 — Structured digest prompt

- `server.py`: add `_build_digest_user_message(groups, channels, days) ->
  list[UserMessage]`:
  - Normalize `groups` and `channels` via `_parse_digest_space_list`.
  - Validate `days` with the same rules used by `_resolve_post_range`
    (reject bool, non-int, `<= 0` with `ConfigError`).
  - Build the instruction text containing the four-row selection matrix,
    the empty-selection message, the per-conversation `list_channel_posts`
    directive, the `list_all_posts` prohibition, sender attribution rules,
    source-ID / timestamp requirement, no-post handling, continuation after
    one unavailable channel, and the prompt-injection safety warning.
  - Return `[UserMessage(content=instruction_text)]`.
- `server.py`: register `@mcp.prompt("channel_digest")` with default
  `groups=""`, `channels=""`, `days=7` returning
  `_build_digest_user_message(...)`.
- `server.py`: refactor the existing `channel_digest://{channel}` prompt to
  delegate to `_build_digest_user_message(groups="", channels=channel,
  days=days)`. No Telegram I/O during `prompts/get`.

Tests: `tests/test_server.py` — defaults, validation, structured message
type, exact workflow text, alias delegation, empty states.

### Phase 6 — Documentation

- `README.md`: replace the placeholder MCP Resources table with live JSON
  entries; add the two new templates; add `set_channel_groups` to the MCP
  Tools table; mention the optional `groups` argument on `add_channel` and
  `add_channel_batch`; document the canonical `channel_digest` prompt and
  the Completion coverage; state explicitly that resources, Completion, and
  the prompt never refresh Telegram content.

### Phase 7 — Verification

- Run focused tests during each phase:
  - `uv run pytest tests/test_db.py -q --tb=short`
  - `uv run pytest tests/test_server.py -q --tb=short`
  - When a single test class is in scope, narrow to
    `uv run pytest tests/test_server.py::TestChannelGroups -q --tb=short`
    (and equivalents for resources, completion, prompt).
- Final: `make check`.
- Diff review: no new module, no new dependency, no Telegram I/O in
  resources / Completion / prompt, `groups` cleared on untrack, replaced on
  upsert, `channel_digest` returns `UserMessage`, README reflects the new
  surface.

## Pitfalls to confirm before implementation

1. `@mcp.completion()` handler signature and the exact return type
   (`mcp.types.Completion`).
2. `list[UserMessage]` is accepted by `@mcp.prompt()` via
   `Prompt.from_function`.
3. `Channel` is frozen; the new `groups` field must be kwarg with a default.
4. `_upgrade_schema` only handles `ALTER TABLE` / `CREATE INDEX`; the new
   table needs its own `CREATE TABLE IF NOT EXISTS` block.
5. Every new sync `_SyncRepository` method needs a `Repository` async
   façade that uses `asyncio.to_thread`.
6. FastMCP URI templates pass `{post_id}` and `{days}` as strings; coerce
   inside the handlers.

## Files touched

- `src/package_tgmcpspy/models.py`
- `src/package_tgmcpspy/db.py`
- `src/package_tgmcpspy/server.py`
- `tests/test_db.py`
- `tests/test_server.py`
- `README.md`
