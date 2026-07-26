# Implementation tasks

All tasks below are pending human review of this change. Do not edit
`openspec/specs/` directly; archive the approved delta only after implementation,
review, and verification.

## 1. Confirm contracts and test strategy

- [x] Review `proposal.md`, `design.md`, and the resource delta with the project
      owner.
- [x] Confirm the installed MCP SDK's public resource, prompt-message, and
      Completion APIs before choosing implementation decorators.
- [x] Inspect the existing focused test modules and identify deterministic test
      fixtures for SQLite, FastMCP registration, and Telegram stubs.
- [x] Define targeted test nodes for resources, group membership, Completion,
      and the structured prompt.

## 2. Extend the cached conversation model with group membership

- [x] Add `groups: tuple[str, ...] = ()` to the `Channel` dataclass while
      preserving existing constructor compatibility.
- [x] Add the `channel_groups` join table (`channel_id INTEGER NOT NULL`,
      `group_name TEXT NOT NULL`, `PRIMARY KEY (channel_id, group_name)`,
      `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE`)
      and an index on `group_name`.
- [x] Add the additive schema upgrade so existing databases receive the new
      table on startup without a manual migration.
- [x] Update `_row_to_channel` to join `channel_groups` and populate the
      `groups` field as a sorted tuple.
- [x] Update all channel serialization assertions to expect the new `groups`
      key.
- [x] Add tests for fresh databases, upgraded databases, and existing rows.

## 3. Implement group persistence and management

- [x] Add synchronous repository support for `upsert_channel(..., groups="")`,
      `set_channel_groups(telegram_id, groups)`, `get_channel_groups(channel_id)`,
      and `list_tracked_channels(groups=None)`.
- [x] Add the corresponding asynchronous repository facade methods.
- [x] Normalize the incoming `groups` string (trim, drop empty segments,
      deduplicate, sort) at the repository boundary.
- [x] Replace existing memberships atomically on every upsert or
      `set_channel_groups` call; do not merge.
- [x] Make `set_tracked(..., False)` clear `channel_groups` rows in the same
      transaction.
- [x] Enforce that only tracked conversations can carry group memberships.
- [x] Expose `add_channel(channel, groups="")`,
      `add_channel_batch(channels, groups="")`, and the new
      `set_channel_groups(channel, groups)` MCP tools.
- [x] Include the `groups` field in every serialized `Channel` response.
- [x] Add tests for upsert with groups, set-channel-groups, list-with-filter,
      untrack-clearing, purge-cascade, normalization, and unknown-channel
      errors.

## 4. Implement live JSON resources

- [x] Add a no-argument lifespan-context accessor suitable for resource handlers.
- [x] Extract shared read helpers for tracked channels, cached resolution, post
      lookup, and date-ranged post lookup.
- [x] Ensure resource resolution never calls Telegram and uses cached IDs or
      usernames only.
- [x] Replace the placeholder `channel://list` resource with live tracked data.
- [x] Replace the placeholder `post://{channel}/{post_id}` resource with live
      cached-post data.
- [x] Add `posts://{channel}/recent/{days}`.
- [x] Add `posts://{channel}/range/{start_date}/{end_date}`.
- [x] Declare `application/json` for every resource.
- [x] Preserve existing tool signatures and behavior.
- [x] Test payload shape, MIME type, ordering, date modes, invalid input,
      missing data, and absence of Telegram I/O.

## 5. Implement MCP Completion

- [x] Register Completion through the installed SDK's supported public API.
- [x] Add deterministic canonical channel candidates from tracked conversations.
- [x] Apply prefix matching, deduplication, and a maximum of 100 channel values.
- [x] Add dependent post-ID candidates for the selected post-resource channel.
- [x] Query and return at most the newest 100 cached IDs, newest first.
- [x] Return empty candidates when dependent channel context is absent or unknown.
- [x] Implement space-aware Completion for the digest `channels` argument.
- [x] Preserve existing input text and exclude already selected channels.
- [x] Leave days and date arguments without custom Completion.
- [x] Add focused Completion tests, including limits and dependency context.

## 6. Implement the structured digest prompt

- [x] Add canonical `channel_digest` prompt arguments `groups=""`,
      `channels=""`, and `days=7`.
- [x] Validate positive non-boolean `days` before producing a message.
- [x] Normalize the `groups` and `channels` strings (trim, drop empty
      segments, deduplicate, preserve first-seen order) before substitution.
- [x] Return a structured FastMCP `PromptMessage` (user role) rather than a
      raw string.
- [x] Embed the agreed prompt text with the four selection rules, the empty
      selection message, per-conversation `list_channel_posts` calls, the
      `list_all_posts` prohibition, sender attribution, source IDs or
      timestamps, no-post handling, continuation after one unavailable
      channel, and prompt-injection safety.
- [x] Preserve the existing prompt registration as a compatibility alias
      that delegates to the canonical builder with `groups=""` and
      `channels={channel}`.
- [x] Add tests for defaults, validation, structured message type, workflow
      text, compatibility behavior, and empty states.

## 7. Update public documentation

- [x] Document live resource URIs and `application/json` payloads in `README.md`.
- [x] Document both post-list resource templates and their validation modes.
- [x] Document group membership, the `groups` field on serialized channels,
      and the `set_channel_groups` tool.
- [x] Document Completion coverage and the newest-100 post-ID limit.
- [x] Document canonical digest prompt arguments, group-based selection, and
      structured tool-orchestration behavior.
- [x] State that resources, Completion, and prompts do not refresh Telegram.

## 8. Verify and review

- [x] Run the required focused pytest command for each changed test module.
- [x] Run formatting and lint/type checks as appropriate during implementation.
- [x] Run `make check` only at the explicit final verification stage.
- [ ] Review the complete diff for privacy, local-only behavior, compatibility,
      and prompt-injection handling.
- [ ] Obtain approval before archiving the change.
- [ ] Archive the approved delta into the main OpenSpec specifications.

## Dependency order

1. Contract review and SDK API confirmation.
2. Model and database migration (groups schema).
3. Group repository/tool behavior.
4. Shared local read helpers and resources.
5. Completion (depends on channel and post repository queries).
6. Structured prompt and compatibility alias.
7. Documentation, tests, final verification, and archive.