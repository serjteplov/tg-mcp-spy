# Implementation tasks

All tasks below are pending human review of this change. Do not edit
`openspec/specs/` directly; archive the approved delta only after implementation,
review, and verification.

## 1. Confirm contracts and test strategy

- [ ] Review `proposal.md`, `design.md`, and the resource delta with the project
      owner.
- [ ] Confirm the installed MCP SDK's public resource, prompt-message, and
      Completion APIs before choosing implementation decorators.
- [ ] Inspect the existing focused test modules and identify deterministic test
      fixtures for SQLite, FastMCP registration, and Telegram stubs.
- [ ] Define targeted test nodes for resources, group membership, Completion,
      and the structured prompt.

## 2. Extend the cached conversation model with group membership

- [ ] Add `groups: tuple[str, ...] = ()` to the `Channel` dataclass while
      preserving existing constructor compatibility.
- [ ] Add the `channel_groups` join table (`channel_id INTEGER NOT NULL`,
      `group_name TEXT NOT NULL`, `PRIMARY KEY (channel_id, group_name)`,
      `FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE`)
      and an index on `group_name`.
- [ ] Add the additive schema upgrade so existing databases receive the new
      table on startup without a manual migration.
- [ ] Update `_row_to_channel` to join `channel_groups` and populate the
      `groups` field as a sorted tuple.
- [ ] Update all channel serialization assertions to expect the new `groups`
      key.
- [ ] Add tests for fresh databases, upgraded databases, and existing rows.

## 3. Implement group persistence and management

- [ ] Add synchronous repository support for `upsert_channel(..., groups="")`,
      `set_channel_groups(telegram_id, groups)`, `get_channel_groups(channel_id)`,
      and `list_tracked_channels(groups=None)`.
- [ ] Add the corresponding asynchronous repository facade methods.
- [ ] Normalize the incoming `groups` string (trim, drop empty segments,
      deduplicate, sort) at the repository boundary.
- [ ] Replace existing memberships atomically on every upsert or
      `set_channel_groups` call; do not merge.
- [ ] Make `set_tracked(..., False)` clear `channel_groups` rows in the same
      transaction.
- [ ] Enforce that only tracked conversations can carry group memberships.
- [ ] Expose `add_channel(channel, groups="")`,
      `add_channel_batch(channels, groups="")`, and the new
      `set_channel_groups(channel, groups)` MCP tools.
- [ ] Include the `groups` field in every serialized `Channel` response.
- [ ] Add tests for upsert with groups, set-channel-groups, list-with-filter,
      untrack-clearing, purge-cascade, normalization, and unknown-channel
      errors.

## 4. Implement live JSON resources

- [ ] Add a no-argument lifespan-context accessor suitable for resource handlers.
- [ ] Extract shared read helpers for tracked channels, cached resolution, post
      lookup, and date-ranged post lookup.
- [ ] Ensure resource resolution never calls Telegram and uses cached IDs or
      usernames only.
- [ ] Replace the placeholder `channel://list` resource with live tracked data.
- [ ] Replace the placeholder `post://{channel}/{post_id}` resource with live
      cached-post data.
- [ ] Add `posts://{channel}/recent/{days}`.
- [ ] Add `posts://{channel}/range/{start_date}/{end_date}`.
- [ ] Declare `application/json` for every resource.
- [ ] Preserve existing tool signatures and behavior.
- [ ] Test payload shape, MIME type, ordering, date modes, invalid input,
      missing data, and absence of Telegram I/O.

## 5. Implement MCP Completion

- [ ] Register Completion through the installed SDK's supported public API.
- [ ] Add deterministic canonical channel candidates from tracked conversations.
- [ ] Apply prefix matching, deduplication, and a maximum of 100 channel values.
- [ ] Add dependent post-ID candidates for the selected post-resource channel.
- [ ] Query and return at most the newest 100 cached IDs, newest first.
- [ ] Return empty candidates when dependent channel context is absent or unknown.
- [ ] Implement space-aware Completion for the digest `channels` argument.
- [ ] Preserve existing input text and exclude already selected channels.
- [ ] Leave days and date arguments without custom Completion.
- [ ] Add focused Completion tests, including limits and dependency context.

## 6. Implement the structured digest prompt

- [ ] Add canonical `channel_digest` prompt arguments `groups=""`,
      `channels=""`, and `days=7`.
- [ ] Validate positive non-boolean `days` before producing a message.
- [ ] Normalize the `groups` and `channels` strings (trim, drop empty
      segments, deduplicate, preserve first-seen order) before substitution.
- [ ] Return a structured FastMCP `UserMessage` rather than a raw string.
- [ ] Embed the agreed prompt text with the four selection rules, the empty
      selection message, per-conversation `list_channel_posts` calls, the
      `list_all_posts` prohibition, sender attribution, source IDs or
      timestamps, no-post handling, continuation after one unavailable
      channel, and prompt-injection safety.
- [ ] Preserve the existing prompt registration as a compatibility alias
      that delegates to the canonical builder with `groups=""` and
      `channels={channel}`.
- [ ] Add tests for defaults, validation, structured message type, workflow
      text, compatibility behavior, and empty states.

## 7. Update public documentation

- [ ] Document live resource URIs and `application/json` payloads in `README.md`.
- [ ] Document both post-list resource templates and their validation modes.
- [ ] Document group membership, the `groups` field on serialized channels,
      and the `set_channel_groups` tool.
- [ ] Document Completion coverage and the newest-100 post-ID limit.
- [ ] Document canonical digest prompt arguments, group-based selection, and
      structured tool-orchestration behavior.
- [ ] State that resources, Completion, and prompts do not refresh Telegram.

## 8. Verify and review

- [ ] Run the required focused pytest command for each changed test module.
- [ ] Run formatting and lint/type checks as appropriate during implementation.
- [ ] Run `make check` only at the explicit final verification stage.
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