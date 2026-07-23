# Tasks: Cache direct messages, groups, and channels

This file breaks the change into concrete, reviewable tasks. Each task references the relevant requirements (R#) and scenarios (S#) from `specs/channels/spec.md`.

## Tasks

- [x] **T1 — Domain models** (R27)
  - Add `ConversationKind` literal (`"channel" | "chat" | "user"`) to `models.py`.
  - Add `kind: ConversationKind` field to `ChannelInfo` and `Channel` (default `"channel"` for safety).
  - Acceptance: `make check` passes.

- [x] **T2 — Database schema** (R31, S27)
  - Add `kind` column to `channels_table` in `db.py` with `String`, `nullable=False`, `default="channel"`.
  - Update `_row_to_channel` to populate `kind` from the row mapping.
  - Acceptance: existing `tgmcpspy.db` loads cleanly; rows get `kind="channel"` on read.

- [x] **T3 — Telegram wrapper** (R28, R29, M3, M4, S21–S24)
  - `get_dialogs`: drop the `entity.broadcast` filter; convert any of `Channel`, `Chat`, `User` to `ChannelInfo` with the right `kind`.
  - `resolve_identifier`: stop forcing `PeerChannel`; let `client.get_entity(parsed)` discriminate; accept `isinstance(entity, (Channel, Chat, User))`.
  - `_resolve_entity`: dispatch by `info.kind` to `PeerChannel`, `PeerChat`, `PeerUser`.
  - `_entity_to_channel_info`: produce the right `kind` and a sensible `title` per entity type (User → "First Last", Chat → `entity.title`, Channel → `entity.title`).
  - Update the `ChannelNotFoundError` message to mention "conversation" where natural.
  - Acceptance: `make check` passes.

- [x] **T4 — Tests** (S21–S27)
  - Update `tests/conftest.py` fake client to support returning `Chat` and `User` entities.
  - `tests/test_telegram.py`: add cases for `resolve_identifier` returning a user, a legacy chat, and a supergroup; broaden `get_dialogs` test to include DMs.
  - `tests/test_db.py`: add a case asserting that pre-existing rows read back with `kind="channel"`.
  - `tests/test_server.py`: add cases for `add_channel` with a user id, `sync_dialogs` picking up DMs and groups, `update_all_channels` updating all kinds, and the 7-day backfill (S26) for `user` and `chat` kinds.
  - Acceptance: `make check` passes with the new tests.

- [x] **T5 — README** (M5)
  - Update `README.md` to describe that tracked "channels" may also be direct messages and group chats, and that `sync_dialogs` mirrors every dialog.
  - Note the `remove_channel` escape hatch for users who do not want every dialog tracked.
  - Acceptance: README reflects the broadened behavior.

- [x] **T6 — Server context and launch hardening**
  - Work around the mcp 1.28.x `ctx.request_context.lifespan_context` bug by
    introducing a module-level `_app_context` bound by `app_lifespan` and a
    `_context(ctx)` helper that ignores the broken `ctx`.
  - Configure `logging.basicConfig` in `main()` and switch `uvicorn.run` to
    `mcp.sse_app()` so SSE and stdio paths launch cleanly. Drop `reload=True`.
  - Acceptance: every MCP tool resolves its lifespan context on mcp 1.28.x;
    `make check` passes.

- [x] **T7 — Username storage consistency**
  - Store `User.username` without a leading `@` (matches `Channel.username`).
  - Update `tests/test_telegram.py::test_resolve_user_entity_returns_kind_user`
    to assert `info.username == "alice"`.
  - Acceptance: `add_channel("alice")` resolves a user tracked with
    `username="alice"`; S22 test passes against the new assertion.

## Cross-cutting constraints

- Never commit secrets; credentials come from env vars only.
- Do not modify `.env`.
- Prefer small, focused commits.
- Run `make check` before marking any task complete.
- Keep functions small and explicitly typed.