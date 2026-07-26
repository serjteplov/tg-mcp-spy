# Expected code changes

This note records the anticipated implementation footprint. It is not an
implementation and does not authorize changes outside the reviewed OpenSpec
scope.

## `src/package_tgmcpspy/models.py`

- Add `is_favorite: bool = False` to the cached `Channel` dataclass while
  preserving existing constructor compatibility.
- Keep favorites local to the cached conversation model; no Telegram model or
  exception type is expected to change.

## `src/package_tgmcpspy/db.py`

### Schema and row mapping

- Add a non-null boolean `is_favorite` column to `channels_table`, defaulting to
  false.
- Extend the additive schema upgrader so existing databases receive the new
  column without a manual migration.
- Populate `Channel.is_favorite` in `_row_to_channel`.

### Repository behavior

- Add synchronous and async-facade methods to set favorite state.
- Reject setting `favorite=true` for an absent or untracked conversation.
- Update `set_tracked(..., False)` to clear `is_favorite` in the same
  transaction.
- Preserve favorite state when an existing conversation is upserted; initialize
  new rows as not favorite.
- Add a query for at most the newest 100 Telegram message IDs for one cached
  channel, ordered descending, for dependent Completion.
- Make tracked-channel ordering deterministic if required by resource and
  Completion tests.
- Keep purge behavior unchanged; deleting channel rows also removes favorite
  state.

## `src/package_tgmcpspy/server.py`

### Shared helpers and context

- Add a no-argument accessor for the lifespan-bound `AppContext`, reusing the
  existing MCP 1.28.x global context workaround.
- Keep the tool-facing context adapter for compatibility.
- Extract small private read helpers so tools and resources share repository
  access, serialization, and domain errors without invoking decorated handlers.
- Add a strict cached-channel resolver that normalizes IDs/usernames but never
  calls `TelegramClientWrapper`.

### Favorite tool

- Add `set_channel_favorite(channel, favorite)` as a local-only MCP tool.
- Return the normal serialized channel object, now including `is_favorite`.
- Preserve all existing tracking and update tools.

### Resources

- Replace the placeholder `channel://list` handler with an async repository read.
- Replace the placeholder `post://{channel}/{post_id}` handler with a local-only
  cached-post read.
- Add `posts://{channel}/recent/{days}`.
- Add `posts://{channel}/range/{start_date}/{end_date}`.
- Declare `application/json` and serialize through existing conversion helpers.
- Reuse current rolling-day and explicit-range validation.
- Keep resource reads lock-free, mutation-free, and free of Telegram I/O.

### Completion

- Register MCP Completion for channel arguments on the post resource, both post
  list templates, and the canonical digest prompt.
- Return one canonical identifier per tracked conversation: username or numeric
  Telegram ID fallback.
- Add dependent post-ID Completion using the selected channel and newest 100
  cached IDs.
- Add comma-aware channel Completion for the digest prompt, preserving prior
  values and excluding duplicates.
- Do not register Completion for days or dates.
- Verify the exact public Completion API available in the installed MCP 1.x
  version before choosing FastMCP versus its underlying MCP server interface.

### Digest prompt

- Add a canonical `channel_digest` registration with `channels=""` and
  `days=7`.
- Return structured FastMCP prompt messages using the SDK prompt message types,
  not a raw string.
- Build an instruction-only user message; do not read posts or call Telegram
  while serving `prompts/get`.
- Validate positive non-boolean days and normalize optional comma-separated
  channels.
- Include favorite fallback, per-channel `list_channel_posts` calls,
  four-to-five-sentence topic summaries, sender formatting, source references,
  explicit empty states, continuation after one unavailable channel, and
  prompt-injection resistance.
- Preserve the existing prompt registration through a compatibility wrapper
  that delegates to the canonical prompt builder.
- Leave `list_all_posts` unchanged and do not use it in the recommended digest
  workflow.

## `README.md`

- Replace placeholder resource documentation with live resource behavior.
- Document both post-list resource templates and JSON media type.
- Document `set_channel_favorite` and the local-only meaning of favorites.
- Document canonical digest prompt arguments, favorite fallback, structured
  prompt/tool-use behavior, and the requirement for a tool-capable MCP client.
- Add concise examples for resources, favorites, and multi-channel digests.
- State that resources, Completion, and prompts do not refresh Telegram data.

## Tests

The exact existing test files must be inspected before editing. Expected focused
coverage includes:

- Resource registration, JSON payloads, MIME type, ordering, validation, and
  not-found behavior.
- Explicit assertions that local resources and Completion never invoke Telegram.
- Fresh-schema and existing-schema favorite behavior.
- Favorite tool success, rejection, persistence, and clearing on untrack.
- Channel Completion, post-ID dependency/limit/order, and comma-separated digest
  Completion.
- Structured prompt message types, defaults, validation, content contract,
  compatibility alias, and empty states.
- Regression coverage for retained read tools.

Implementation should run one changed test module at a time with the project's
required targeted pytest command. `make check` is reserved for explicit final
verification.

## OpenSpec lifecycle

- Keep this change under `openspec/changes/mcp-resources-and-digest/` during
  implementation and review.
- Do not edit `openspec/specs/` directly.
- After implementation, tests, review, and approval, archive the change so its
  delta is merged into the current specifications.

## Files not expected to change

- `src/package_tgmcpspy/telegram.py`: no Telegram-side favorite or resource
  behavior is added.
- `src/package_tgmcpspy/config.py`: no new environment configuration is needed.
- `pyproject.toml`: no dependency or tool configuration change is planned.
