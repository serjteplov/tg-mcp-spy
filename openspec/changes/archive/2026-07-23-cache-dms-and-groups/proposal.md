# Proposal: Cache direct messages, groups, and channels

## Problem

`tg-mcp-spy` currently caches only Telegram broadcast channels. The Telethon wrapper rejects anything that is not a `Channel` entity, and `sync_dialogs` filters on `entity.broadcast`. Direct messages with users, legacy small-group chats, and supergroups cannot be tracked, even when the user session has access to them.

The data model already generalizes naturally — the dataclass is named `Channel` but holds only `telegram_id`, `username`, and `title`, all of which apply to users and chats as well. The blocker is purely in the wrapper layer and the missing `kind` discriminator.

## Goal

Allow the same MCP tools to cache any Telegram conversation the user session can read:

- Direct messages with users.
- Legacy small-group chats (`Chat` entities, negative IDs).
- Channels (public and private broadcast, plus supergroups).

Tool names stay the same. `sync_dialogs` mirrors every dialog. First-add backfill stays at the 7-day default for every kind.

## Scope

### In scope

- New `kind` field on `ChannelInfo` and `Channel` with values `channel | chat | user`.
- New SQLite column `kind` on `channels_table` (default `'channel'` for existing rows).
- `TelegramClientWrapper.resolve_identifier` accepts `User`, `Chat`, and `Channel` entities and returns the right `kind`.
- `TelegramClientWrapper.get_dialogs` returns every conversation kind, not just broadcast channels.
- `TelegramClientWrapper._resolve_entity` dispatches by `kind` to `PeerUser`, `PeerChat`, or `PeerChannel`.
- README updated to reflect the broadened behavior.

### Out of scope

- Renaming MCP tools (`add_channel` keeps its name even when targeting a user).
- Grouping logic (megagroup migration, member lists) — we only cache messages.
- Media download/storage — still text and metadata only.
- Per-kind backfill windows or per-kind TTL overrides.
- Migrating existing databases with channels that might re-resolve as different kinds — rows keep whatever kind they were first stored as; re-syncing picks up the new kind.

## Acceptance criteria

1. `make check` passes after the change.
2. `add_channel("6199205118")` succeeds for a user id, `add_channel("-1001234567890")` still works for a channel, and a legacy chat id also resolves.
3. `sync_dialogs` includes DMs, legacy chats, and channels from the user's Telegram dialog list.
4. Existing rows in `tgmcpspy.db` keep working without a manual migration step (default `kind='channel'`).
5. All new behavior is covered by deterministic unit tests.
6. README documents the broader behavior.
7. OpenSpec delta-spec and design documents are approved and archived.

## Risks

- A user id and a channel id share the same numeric namespace on Telegram. `normalize_identifier` cannot disambiguate by shape — resolution must try `get_entity` and let Telethon return the right type.
- `sync_dialogs` will add many more tracked items than before (every DM and legacy chat). Users may want to remove most of them locally; the existing `remove_channel` tool handles that.
- A user with no public username has a NULL `username`. Tool lookups by username must already handle that — they do, via `_resolve_db_channel` falling back to `get_channel_by_telegram_id`.
- Caching personal-chat content raises the privacy stakes of the local SQLite file and the session string. Same mitigations apply: env-only credentials, no logging of post text, local bind.
- `add_channel` and friends still use the literal word "channel" in their tool name even when the underlying entity is a user or chat. Confusing but documented; renaming would break existing MCP clients.

## Data retention and security

- No changes to TTL or retention policy.
- Credentials remain env-only and never logged.
- Post text is never written to logs.
- The local SQLite file now contains more sensitive content (DM history); host-side filesystem protections matter more.

## Dependencies

- No new runtime or dev dependencies. Existing `telethon`, `sqlalchemy`, `pytest-asyncio` cover the change.

## Estimated effort

Small. One implementation slice covering the four files (`models.py`, `db.py`, `telegram.py`, plus tests), plus a README note.