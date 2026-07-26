# Change: Live MCP resources, Completion, and channel digests

## Status

PROPOSED — awaiting review before implementation.

## Why

The server currently advertises `channel://list` and
`post://{channel}/{post_id}`, but both resources return placeholders instead of
cached data. Clients must know to call equivalent tools, cannot discover useful
resource-template completions, and cannot address cached channel post lists as
resources.

The current digest prompt accepts one channel and eagerly formats cached posts
as plain text. It does not follow the structured FastMCP message pattern, cannot
select multiple conversations, has no group-based selection, and does not
define safe, traceable summarization behavior.

This change makes the read-only MCP surface useful while preserving the existing
tool API and the project's local-cache and privacy boundaries.

## What changes

### Live resources

- Replace `channel://list` with a live JSON resource containing all tracked
  conversations.
- Replace `post://{channel}/{post_id}` with a live JSON resource template for a
  single cached post.
- Add `posts://{channel}/recent/{days}` for an inclusive rolling UTC window.
- Add `posts://{channel}/range/{start_date}/{end_date}` for an inclusive explicit
  UTC range.
- Advertise all resource payloads as `application/json`.
- Resolve resource identifiers only against the local cache; resource reads
  never contact Telegram or mutate state.

### Group membership

- Persist a `groups` list (zero or more user-defined string labels) for each
  cached conversation through a normalized local join table, defaulting to an
  empty list for new and existing rows.
- Expose the `groups` field on every serialized `Channel` so clients and
  prompts can filter locally without Telegram I/O.
- Add `set_channel_groups(channel, groups)` to replace group memberships for
  an existing tracked conversation without contacting Telegram.
- Extend `add_channel(channel, groups="")` and `add_channel_batch(channels,
  groups="")` to accept an optional space-separated `groups` string at
  insertion time.
- Keep groups as a subset of tracked conversations; clearing tracked state
  removes group memberships in the same transaction.
- Do not map local groups to Telegram folders, channels, pins, memberships,
  or any server-side taxonomy.

### MCP Completion

- Complete canonical tracked-conversation identifiers for resource-template and
  digest-prompt channel arguments.
- Use the cached username when present and otherwise the numeric Telegram ID.
- Complete at most the newest 100 cached post IDs for the channel already
  selected in `post://{channel}/{post_id}`.
- Support space-separated completion for the digest's `channels` argument while
  preserving prior selections and excluding duplicates.
- Do not complete `days`, `start_date`, or `end_date`.

### Structured digest prompt

- Add a canonical `channel_digest` prompt with `groups: str = ""`,
  `channels: str = ""`, and `days: int = 7`. Both `groups` and `channels` are
  space-separated strings; the prompt builder normalizes them on retrieval.
- Return structured FastMCP prompt messages rather than a raw string.
- Selection rules the prompt enforces:
  - If both `groups` and `channels` are empty, instruct the model to respond
    with a "provide at least one group or channel" message and stop.
  - If `groups` is empty and `channels` is non-empty, instruct the model to
    process the listed channels in first-seen order, with no group filter.
  - If `channels` is empty and `groups` is non-empty, instruct the model to
    call `list_tracked_channels` and select every tracked conversation whose
    `groups` field intersects the requested groups.
  - If both are non-empty, instruct the model to start from the listed
    channels and keep only entries whose `groups` intersect the requested
    groups.
  - If the resulting selection is empty, instruct the model to report that no
    tracked conversations match and stop.
- For each selected conversation, instruct the model to call
  `list_channel_posts(channel, days=days)` once.
- Forbid calling update tools, contacting Telegram directly, or using
  `list_all_posts` for the normal digest workflow.
- Require one factual four-to-five-sentence topic digest per conversation,
  sender attribution with the agreed fallback chain, explicit empty-state
  messages, and source post IDs or timestamps.
- Treat cached Telegram post text as untrusted content and explicitly prohibit
  following instructions contained in posts.
- Preserve the existing prompt registration as a compatibility alias that
  maps its singular channel argument to the canonical prompt behavior with
  `groups=""` and `channels={channel}`.

## Scope

### In scope

- Read-only MCP resources and resource templates backed by SQLite.
- Local-only channel resolution for resources and Completion.
- Local group-membership persistence, migration, serialization, and
  management through a normalized join table.
- MCP Completion for channel and dependent post-ID arguments.
- A structured, tool-orchestrating digest prompt with groups-based selection.
- Focused unit tests, public documentation updates, and final project checks.

### Out of scope

- Telegram-side folders, pins, joins, leaves, or subscription changes.
- Telegram refreshes initiated by resources, Completion, or digest prompts.
- Resource subscriptions, notifications, or server-pushed updates.
- A built-in LLM, Anthropic SDK integration, or server-side summarization.
- Removal of existing read tools.
- Completion for temporal arguments.
- Pagination or response-shape redesign for existing post-list tools.

## Compatibility

- `list_tracked_channels`, `get_post`, `list_channel_posts`, and
  `list_all_posts` remain available with their current call signatures.
- Existing resource URIs remain registered but change from placeholder payloads
  to live cached data.
- Channel payloads gain the additive `groups` field (a tuple of strings).
  `add_channel` and `add_channel_batch` accept an optional `groups`
  argument; older callers that omit it continue to work unchanged.
- Existing database rows are migrated automatically with an empty `groups`
  list; the new `channel_groups` table is created on startup if it does not
  exist, and no manual migration is required.
- The canonical prompt uses standard MCP prompt naming and structured messages;
  the existing prompt registration remains as a compatibility alias.
- No new runtime dependency is planned.

## Risks

- Resources expose cached private conversation content to any client authorized
  to access this local MCP server; the existing local-bind and filesystem
  protections remain essential.
- Large date ranges can produce large JSON resources because pagination is not
  part of this change.
- Prompt execution depends on an MCP client/model that can follow prompt
  instructions and invoke tools; `prompts/get` alone does not generate a digest.
- Completion integration must match the APIs available in the pinned MCP 1.x
  dependency and the project's lifespan-context workaround.
- Schema and tracking transitions must preserve the invariant that only
  tracked conversations may have non-empty group memberships.
- Telegram post text can contain prompt-injection attempts; the digest prompt
  must frame it as untrusted data.

## Success criteria

- All four resource URIs return live, deterministic JSON from the local cache.
- Resource reads and Completion perform no Telegram I/O and no mutation.
- Existing read tools continue to behave as before.
- Group membership survives restart, migrates safely, and is cleared on
  untracking. Re-upserting an existing channel replaces its groups; new
  channels default to an empty list.
- Completion returns the agreed canonical channels and bounded dependent post
  IDs, including space-separated digest completion.
- The canonical digest prompt returns structured FastMCP messages with the
  agreed groups-based selection, safety, summarization, attribution, and
  empty-state rules.
- Focused tests and the final `make check` pass before the change is considered
  implemented.
