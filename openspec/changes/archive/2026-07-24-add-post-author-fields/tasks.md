# Tasks: Add post author fields (`username`, `display_name`)

- [x] Extend `MessageInfo` and `Post` in `src/package_tgmcpspy/models.py`
  with `username: str | None` and `display_name: str | None`.
- [x] Add `username` and `display_name` columns plus
  `ix_posts_display_name` index to `posts_table` in
  `src/package_tgmcpspy/db.py`.
- [x] Extend `_upgrade_schema` with idempotent `ALTER TABLE` rows for the
  two columns and a `CREATE INDEX` row for the new index.
- [x] Extend `_row_to_post` to read the new columns.
- [x] Extend `_SyncRepository.upsert_posts` to write the new fields.
- [x] Add private `_sender_fields(message)` helper in
  `src/package_tgmcpspy/telegram.py` covering: real name + username,
  real name only, username only, neither, service message, deleted
  sender, non-User sender.
- [x] Use the helper in `fetch_messages_since` and `fetch_messages_after`
  via `_message_to_message_info`.
- [x] Add `tests/test_db.py` round-trip tests (both populated, both None)
  and schema-upgrade test on an existing DB.
- [x] Add `tests/test_telegram.py` unit tests for `_sender_fields` and
  fetch helper mapping.
- [x] Add `tests/test_server.py` payload-shape tests for `get_post` and
  `list_channel_posts`.
- [x] Update `README.md` tool-output description to mention the new keys.
- [x] Run `uv run pytest tests/test_db.py tests/test_telegram.py
  tests/test_server.py -q --tb=short`.
- [x] Run `make check` at the end.
