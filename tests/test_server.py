"""Tests for the FastMCP server tools and helpers.

Importing ``package_tgmcpspy.server`` triggers FastMCP tool registration,
which requires pydantic models that fail outside a real MCP server context.
All server imports are therefore deferred to test methods and helpers.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from package_tgmcpspy.models import (
    ChannelInfo,
    ChannelNotFoundError,
    ConfigError,
    ConversationKind,
    MessageInfo,
)


class TestParseDateRange:
    """Tests for _parse_date_range date handling (R16)."""

    def test_yyyy_mm_dd_interpreted_as_utc(self) -> None:
        from package_tgmcpspy.server import _parse_date_range

        start, end = _parse_date_range("2026-07-14", "2026-07-19")
        assert start == datetime(2026, 7, 14, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 7, 19, 23, 59, 59, 999999, tzinfo=UTC)

    def test_iso_timestamp_interpreted_as_utc(self) -> None:
        from package_tgmcpspy.server import _parse_date_range

        start, end = _parse_date_range(
            "2026-07-14T10:00:00+00:00",
            "2026-07-19T15:30:00Z",
        )
        assert start.hour == 10
        assert end.hour == 15

    def test_iso_without_tz_defaults_to_utc(self) -> None:
        from package_tgmcpspy.server import _parse_date_range

        start, end = _parse_date_range(
            "2026-07-14T10:00:00",
            "2026-07-19T15:30:00",
        )
        assert start.tzinfo is not None
        assert end.tzinfo is not None


class TestResolvePostRange:
    """Tests for _resolve_post_range selection-mode validation."""

    def test_rolling_days_uses_inclusive_utc_interval(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        now = datetime(2026, 7, 23, 12, 0, 0, tzinfo=UTC)
        start, end = _resolve_post_range(start_date=None, end_date=None, days=3, now=now)
        assert start == datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)
        assert end == now

    def test_explicit_range_passes_through(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        start, end = _resolve_post_range(start_date="2026-07-14", end_date="2026-07-19", days=None)
        assert start == datetime(2026, 7, 14, 0, 0, 0, tzinfo=UTC)
        assert end == datetime(2026, 7, 19, 23, 59, 59, 999999, tzinfo=UTC)

    def test_no_mode_raises(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        with pytest.raises(ConfigError):
            _resolve_post_range(start_date=None, end_date=None, days=None)

    def test_missing_start_date_raises(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        with pytest.raises(ConfigError):
            _resolve_post_range(start_date=None, end_date="2026-07-19", days=None)

    def test_missing_end_date_raises(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        with pytest.raises(ConfigError):
            _resolve_post_range(start_date="2026-07-14", end_date=None, days=None)

    def test_mixed_modes_raises(self) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        with pytest.raises(ConfigError):
            _resolve_post_range(start_date="2026-07-14", end_date="2026-07-19", days=3)

    @pytest.mark.parametrize("bad", [0, -1, -30, 1.5, True, False])
    def test_invalid_days_raises(self, bad: object) -> None:
        from package_tgmcpspy.server import _resolve_post_range

        with pytest.raises(ConfigError):
            _resolve_post_range(start_date=None, end_date=None, days=bad)  # type: ignore[arg-type]


class TestParseBatchIdentifiers:
    """Tests for _parse_batch_identifiers input parsing."""

    def test_trims_whitespace(self) -> None:
        from package_tgmcpspy.server import _parse_batch_identifiers

        assert _parse_batch_identifiers("  alice  ,  bob  ") == ["alice", "bob"]

    def test_ignores_empty_segments(self) -> None:
        from package_tgmcpspy.server import _parse_batch_identifiers

        assert _parse_batch_identifiers("alice,, ,bob,") == ["alice", "bob"]

    def test_deduplicates_preserving_first_seen_order(self) -> None:
        from package_tgmcpspy.server import _parse_batch_identifiers

        assert _parse_batch_identifiers("a,b,a,c,b") == ["a", "b", "c"]

    def test_all_empty_raises(self) -> None:
        from package_tgmcpspy.server import _parse_batch_identifiers

        with pytest.raises(ConfigError):
            _parse_batch_identifiers(" , ,, ,")
        with pytest.raises(ConfigError):
            _parse_batch_identifiers("")


class TestResolveDbChannel:
    """Tests for _resolve_db_channel helper (R20)."""

    async def test_resolve_by_username(self, app_context: Any, fake_client: Any) -> None:
        from package_tgmcpspy.server import _resolve_db_channel

        fake_client.add_channel(telegram_id=100, username="testchan", title="Test")
        await app_context.repo.upsert_channel(fake_client._channels["testchan"], is_tracked=True)

        result = await _resolve_db_channel(app_context, "testchan")
        assert result.telegram_id == 100

    async def test_resolve_by_numeric_id(self, app_context: Any, fake_client: Any) -> None:
        from package_tgmcpspy.server import _resolve_db_channel

        fake_client.add_channel(telegram_id=200, username=None, title="IDChan")
        await app_context.repo.upsert_channel(fake_client._channels["200"], is_tracked=True)

        result = await _resolve_db_channel(app_context, "200")
        assert result.telegram_id == 200

    async def test_resolve_unknown_raises(self, app_context: Any, fake_client: Any) -> None:
        from package_tgmcpspy.server import _resolve_db_channel

        with pytest.raises(ChannelNotFoundError):
            await _resolve_db_channel(app_context, "nonexistent")

    async def test_resolve_negative_100_id(self, app_context: Any, fake_client: Any) -> None:
        from package_tgmcpspy.server import _resolve_db_channel

        fake_client.add_channel(telegram_id=300, username=None, title="Neg")
        await app_context.repo.upsert_channel(fake_client._channels["300"], is_tracked=True)

        result = await _resolve_db_channel(app_context, "-100300")
        assert result.telegram_id == 300


class TestAddChannelAll:
    """S1, S21 — add_channel_all upserts dialogs as tracked, including DMs and chats."""

    async def test_add_channel_all_upserts_tracked(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=10, username="chan_a", title="A")
        fake_client.add_channel(telegram_id=20, username="chan_b", title="B")

        result = await _call_tool(app_context, "add_channel_all")
        assert result["synced"] == 2
        assert len(result["channels"]) == 2

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 2

    async def test_add_channel_all_includes_users_and_chats(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """S21 — add_channel_all mirrors DMs, legacy chats, and broadcast channels."""
        fake_client.add_channel(telegram_id=100, title="Alice", kind="user")
        fake_client.add_channel(telegram_id=200, title="Family", kind="chat")
        fake_client.add_channel(telegram_id=300, username="news", title="News", kind="channel")

        result = await _call_tool(app_context, "add_channel_all")
        assert result["synced"] == 3

        kinds = {row["telegram_id"]: row["kind"] for row in result["channels"]}
        assert kinds == {100: "user", 200: "chat", 300: "channel"}

        tracked = await app_context.repo.list_tracked_channels()
        assert {row.kind for row in tracked} == {"user", "chat", "channel"}

    async def test_add_channel_all_does_not_fetch_messages(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """R20/M — add_channel_all never calls fetch_messages_*."""
        fake_client.add_channel(telegram_id=10, username="chan_a", title="A")
        fake_client.add_channel(telegram_id=20, username="chan_b", title="B")
        fake_client.add_message(10, 1, "msg-a", timestamp=datetime.now(UTC))
        fake_client.add_message(20, 1, "msg-b", timestamp=datetime.now(UTC))

        fake_client.fetch_messages_since = _fail_fetch
        fake_client.fetch_messages_after = _fail_fetch

        result = await _call_tool(app_context, "add_channel_all")
        assert result["synced"] == 2


class TestAddChannelBatch:
    """Tests for add_channel_batch sequential processing and partial failures."""

    async def test_batch_trims_dedupes_and_processes_in_order(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        fake_client.add_channel(telegram_id=2, username="b", title="B")

        result = await _call_tool(app_context, "add_channel_batch", channels="  a , , b , a ,")

        assert [entry["identifier"] for entry in result] == ["a", "b"]
        assert [entry["status"] for entry in result] == ["added", "added"]
        assert all("channel" in entry for entry in result)

    async def test_batch_already_tracked_reported(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)

        result = await _call_tool(app_context, "add_channel_batch", channels="a")

        assert len(result) == 1
        assert result[0]["status"] == "already_tracked"
        assert result[0]["channel"]["telegram_id"] == 1

    async def test_batch_continues_after_partial_failure(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        fake_client.add_channel(telegram_id=3, username="c", title="C")

        result = await _call_tool(app_context, "add_channel_batch", channels="a,b,c")

        assert [entry["identifier"] for entry in result] == ["a", "b", "c"]
        assert result[0]["status"] == "added"
        assert result[1]["status"] == "error"
        assert result[2]["status"] == "added"

    async def test_batch_empty_input_raises(self, app_context: Any) -> None:
        with pytest.raises(ConfigError):
            await _call_tool(app_context, "add_channel_batch", channels=" , , ")

    async def test_batch_never_fetches_messages(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        fake_client.add_message(1, 1, "msg", timestamp=datetime.now(UTC))
        fake_client.fetch_messages_since = _fail_fetch
        fake_client.fetch_messages_after = _fail_fetch

        result = await _call_tool(app_context, "add_channel_batch", channels="a")

        assert result[0]["status"] == "added"


class TestListTrackedChannels:
    """S2 — list_tracked_channels filters correctly."""

    async def test_list_tracked_channels_returns_only_tracked(self, app_context: Any) -> None:
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=False
        )

        result = await _call_tool(app_context, "list_tracked_channels")
        assert len(result) == 1
        assert result[0]["telegram_id"] == 1


class TestAddRemoveChannel:
    """S3–S4 — add_channel / remove_channel only change local flag."""

    async def test_add_channel_marks_tracked(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=50, username="new_chan", title="New")

        result = await _call_tool(app_context, "add_channel", channel="new_chan")
        assert result["is_tracked"] is True

    async def test_add_user_by_numeric_id(self, app_context: Any, fake_client: Any) -> None:
        """S22 — numeric user id resolves to a tracked user."""
        fake_client.add_channel(
            telegram_id=6199205118, username="alice", title="Alice", kind="user"
        )

        result = await _call_tool(app_context, "add_channel", channel="6199205118")
        assert result["telegram_id"] == 6199205118
        assert result["kind"] == "user"
        assert result["is_tracked"] is True

    async def test_add_legacy_chat_by_id(self, app_context: Any, fake_client: Any) -> None:
        """S23 — negative chat id resolves to a tracked chat."""
        fake_client.add_channel(telegram_id=123456789, title="Family", kind="chat")

        result = await _call_tool(app_context, "add_channel", channel="123456789")
        assert result["telegram_id"] == 123456789
        assert result["kind"] == "chat"

    async def test_add_supergroup_by_id(self, app_context: Any, fake_client: Any) -> None:
        """S24 — large negative id resolves to a tracked channel."""
        fake_client.add_channel(
            telegram_id=1234567890, username="sg", title="Supergroup", kind="channel"
        )

        result = await _call_tool(app_context, "add_channel", channel="-1001234567890")
        assert result["telegram_id"] == 1234567890
        assert result["kind"] == "channel"

    async def test_remove_channel_untracks(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=60, username="rem_chan", title="Rem")
        await app_context.repo.upsert_channel(fake_client._channels["rem_chan"], is_tracked=True)

        result = await _call_tool(app_context, "remove_channel", channel="rem_chan")
        assert result["is_tracked"] is False

    async def test_remove_channel_not_found_raises(self, app_context: Any) -> None:
        with pytest.raises(ChannelNotFoundError):
            await _call_tool(app_context, "remove_channel", channel="ghost")


class TestUpdateChannel:
    """S5–S6 — update_channel initial backfill vs incremental."""

    async def test_update_channel_initial_backfill(
        self, app_context: Any, fake_client: Any
    ) -> None:
        from package_tgmcpspy.server import _update_channel

        fake_client.add_channel(telegram_id=100, username="backfill", title="Backfill")
        now = datetime.now(UTC)
        fake_client.add_message(100, 1, "old", timestamp=now - timedelta(days=3))
        fake_client.add_message(100, 2, "recent", timestamp=now - timedelta(days=1))

        result = await _update_channel(app_context, "backfill")
        assert result["fetched"] == 2
        assert result["inserted"] == 2
        assert result["last_message_id"] == 2

    async def test_update_channel_incremental(self, app_context: Any, fake_client: Any) -> None:
        from package_tgmcpspy.server import _update_channel

        fake_client.add_channel(telegram_id=200, username="incr", title="Incr")
        now = datetime.now(UTC)
        fake_client.add_message(200, 10, "first", timestamp=now - timedelta(days=1))
        await _update_channel(app_context, "incr")

        fake_client.add_message(200, 11, "second", timestamp=now)
        result = await _update_channel(app_context, "incr")
        assert result["fetched"] == 1
        assert result["inserted"] == 1
        assert result["last_message_id"] == 11

    async def test_update_channel_backfill_7_days_for_user(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """S26/R32 — first-add backfill stays at 7 days for the user kind."""
        from package_tgmcpspy.server import _update_channel

        fake_client.add_channel(telegram_id=700, title="Alice", kind="user")
        now = datetime.now(UTC)
        fake_client.add_message(700, 1, "recent", timestamp=now - timedelta(days=2))
        fake_client.add_message(700, 2, "stale", timestamp=now - timedelta(days=10))

        result = await _update_channel(app_context, "700")
        assert result["fetched"] == 1
        assert result["inserted"] == 1

        stored = await app_context.repo.get_channel_by_telegram_id(700)
        assert stored is not None
        posts = await app_context.repo.list_channel_posts(stored.id, now - timedelta(days=30), now)
        assert {post.telegram_message_id for post in posts} == {1}

    async def test_update_channel_backfill_7_days_for_chat(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """S26/R32 — first-add backfill stays at 7 days for the chat kind."""
        from package_tgmcpspy.server import _update_channel

        fake_client.add_channel(telegram_id=800, title="Family", kind="chat")
        now = datetime.now(UTC)
        fake_client.add_message(800, 1, "recent", timestamp=now - timedelta(days=3))
        fake_client.add_message(800, 2, "stale", timestamp=now - timedelta(days=15))

        result = await _update_channel(app_context, "800")
        assert result["fetched"] == 1
        assert result["inserted"] == 1

        stored = await app_context.repo.get_channel_by_telegram_id(800)
        assert stored is not None
        posts = await app_context.repo.list_channel_posts(stored.id, now - timedelta(days=30), now)
        assert {post.telegram_message_id for post in posts} == {1}

    async def test_update_channel_uses_configured_backfill_for_each_kind(
        self, app_context: Any, fake_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Configured backfill_days applies to all conversation kinds on first update."""
        _app_context_with_backfill(monkeypatch, app_context, backfill_days=14)
        now = datetime.now(UTC)
        for telegram_id, kind in [(10, "user"), (20, "chat"), (30, "channel")]:
            fake_client.add_channel(telegram_id=telegram_id, title=f"T{telegram_id}", kind=kind)
            fake_client.add_message(telegram_id, 1, "inside", timestamp=now - timedelta(days=10))
            fake_client.add_message(telegram_id, 2, "outside", timestamp=now - timedelta(days=20))

        from package_tgmcpspy.server import _update_channel

        for _telegram_id, identifier in [(10, "10"), (20, "20"), (30, "30")]:
            await _update_channel(app_context, identifier)

        for telegram_id in (10, 20, 30):
            stored = await app_context.repo.get_channel_by_telegram_id(telegram_id)
            assert stored is not None
            posts = await app_context.repo.list_channel_posts(
                stored.id, now - timedelta(days=30), now
            )
            assert {post.telegram_message_id for post in posts} == {1}

    async def test_update_channel_incremental_uses_last_message_id(
        self, app_context: Any, fake_client: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Incremental updates keep using last_message_id regardless of backfill_days."""
        _app_context_with_backfill(monkeypatch, app_context, backfill_days=14)
        from package_tgmcpspy.server import _update_channel

        fake_client.add_channel(telegram_id=400, username="incr", title="Incr")
        await app_context.repo.upsert_channel(fake_client._channels["incr"], is_tracked=True)
        now = datetime.now(UTC)
        fake_client.add_message(400, 100, "first", timestamp=now - timedelta(days=20))
        await _update_channel(app_context, "incr")

        # Seed the cached last_message_id so the next update uses incremental mode.
        await app_context.repo.update_channel_stats(
            (await app_context.repo.get_channel_by_telegram_id(400)).id,
            100,
            now,
        )

        fake_client.add_message(400, 101, "second", timestamp=now - timedelta(days=15))
        result = await _update_channel(app_context, "incr")
        assert result["fetched"] == 1
        assert result["inserted"] == 1
        assert result["last_message_id"] == 101


class TestUpdateAllChannels:
    """S7, S17 — update_all_channels sequential update and partial failure."""

    async def test_update_all_channels_updates_each(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=10, username="a", title="A")
        fake_client.add_channel(telegram_id=20, username="b", title="B")
        now = datetime.now(UTC)
        fake_client.add_message(10, 1, "post-a", timestamp=now)
        fake_client.add_message(20, 1, "post-b", timestamp=now)

        await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)
        await app_context.repo.upsert_channel(fake_client._channels["b"], is_tracked=True)

        result = await _call_tool(app_context, "update_all_channels")
        assert len(result["results"]) == 2
        assert result["errors"] == {}

    async def test_update_all_channels_handles_all_kinds(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """S25 — update_all_channels updates DM, chat, and channel kinds sequentially."""
        items: list[tuple[int, ConversationKind]] = [
            (101, "user"),
            (202, "chat"),
            (303, "channel"),
        ]
        for telegram_id, kind in items:
            fake_client.add_channel(telegram_id=telegram_id, title=f"Title{telegram_id}", kind=kind)
            fake_client.add_message(
                telegram_id, 1, f"msg-{telegram_id}", timestamp=datetime.now(UTC)
            )
            await app_context.repo.upsert_channel(
                ChannelInfo(
                    telegram_id=telegram_id,
                    username=None,
                    title=f"Title{telegram_id}",
                    kind=kind,
                ),
                is_tracked=True,
            )

        result = await _call_tool(app_context, "update_all_channels")
        assert result["errors"] == {}
        assert len(result["results"]) == 3

        for entry in result["results"]:
            assert entry["fetched"] >= 1
            assert entry["last_message_id"] >= 1

    async def test_update_all_channels_partial_failure(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=10, username="good", title="Good")
        now = datetime.now(UTC)
        fake_client.add_message(10, 1, "post-good", timestamp=now)

        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=10, username="good", title="Good"), is_tracked=True
        )
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=99, username="bad", title="Bad"), is_tracked=True
        )

        result = await _call_tool(app_context, "update_all_channels")
        assert len(result["results"]) >= 1
        assert "bad" in result["errors"]


class TestGetPost:
    """S8–S9 — get_post success and not-found."""

    async def test_get_post_returns_cached_post(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=100, username="postchan", title="Posts")
        ch = await app_context.repo.upsert_channel(
            fake_client._channels["postchan"], is_tracked=True
        )
        now = datetime.now(UTC)
        await app_context.repo.upsert_posts(
            ch.id, [MessageInfo(telegram_message_id=42, timestamp_utc=now, text="hello")]
        )

        result = await _call_tool(app_context, "get_post", channel="postchan", post_id=42)
        assert result["text"] == "hello"

    async def test_get_post_not_found_raises(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=100, username="postchan", title="Posts")
        await app_context.repo.upsert_channel(fake_client._channels["postchan"], is_tracked=True)

        with pytest.raises(ChannelNotFoundError):
            await _call_tool(app_context, "get_post", channel="postchan", post_id=99)


class TestListChannelPosts:
    """S10, S19 — list_channel_posts inclusive date bounds, full text, and rolling days."""

    async def test_list_channel_posts_inclusive_range(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=100, username="datechan", title="Dates")
        ch = await app_context.repo.upsert_channel(
            fake_client._channels["datechan"], is_tracked=True
        )
        base = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
        await app_context.repo.upsert_posts(
            ch.id,
            [
                MessageInfo(telegram_message_id=1, timestamp_utc=base, text="inside"),
                MessageInfo(
                    telegram_message_id=2,
                    timestamp_utc=base + timedelta(days=1),
                    text="inside-end",
                ),
                MessageInfo(
                    telegram_message_id=3,
                    timestamp_utc=base - timedelta(days=1),
                    text="before",
                ),
            ],
        )

        result = await _call_tool(
            app_context,
            "list_channel_posts",
            channel="datechan",
            start_date="2026-07-15",
            end_date="2026-07-16",
        )
        ids = {p["telegram_message_id"] for p in result}
        assert ids == {1, 2}

    async def test_list_channel_posts_returns_full_text(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=100, username="textchan", title="Text")
        ch = await app_context.repo.upsert_channel(
            fake_client._channels["textchan"], is_tracked=True
        )
        now = datetime.now(UTC)
        await app_context.repo.upsert_posts(
            ch.id, [MessageInfo(telegram_message_id=1, timestamp_utc=now, text="Hello, world!")]
        )

        result = await _call_tool(
            app_context,
            "list_channel_posts",
            channel="textchan",
            start_date="2026-01-01",
            end_date="2030-12-31",
        )
        assert result[0]["text"] == "Hello, world!"

    async def test_list_channel_posts_rolling_days_inclusive(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=100, username="dayschan", title="Days")
        ch = await app_context.repo.upsert_channel(
            fake_client._channels["dayschan"], is_tracked=True
        )
        base = datetime.now(UTC) - timedelta(hours=1)
        await app_context.repo.upsert_posts(
            ch.id,
            [
                MessageInfo(telegram_message_id=1, timestamp_utc=base, text="recent"),
                MessageInfo(
                    telegram_message_id=2,
                    timestamp_utc=base - timedelta(days=1),
                    text="inside",
                ),
                MessageInfo(
                    telegram_message_id=3,
                    timestamp_utc=base - timedelta(days=3),
                    text="outside",
                ),
                MessageInfo(
                    telegram_message_id=4,
                    timestamp_utc=base + timedelta(days=1),
                    text="future",
                ),
            ],
        )

        result = await _call_tool(
            app_context,
            "list_channel_posts",
            channel="dayschan",
            days=2,
        )
        ids = {p["telegram_message_id"] for p in result}
        assert ids == {1, 2}

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"start_date": "2026-07-15"},
            {"end_date": "2026-07-19"},
            {"start_date": "2026-07-15", "days": 3},
            {"end_date": "2026-07-19", "days": 3},
            {"start_date": "2026-07-15", "end_date": "2026-07-19", "days": 3},
        ],
    )
    async def test_list_channel_posts_invalid_modes_raise(
        self, app_context: Any, fake_client: Any, kwargs: dict[str, object]
    ) -> None:
        fake_client.add_channel(telegram_id=100, username="chan", title="Chan")
        await app_context.repo.upsert_channel(fake_client._channels["chan"], is_tracked=True)

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "list_channel_posts", channel="chan", **kwargs)

    @pytest.mark.parametrize("bad_days", [0, -1, 1.5, True, False])
    async def test_list_channel_posts_invalid_days_raise(
        self, app_context: Any, fake_client: Any, bad_days: object
    ) -> None:
        fake_client.add_channel(telegram_id=100, username="chan", title="Chan")
        await app_context.repo.upsert_channel(fake_client._channels["chan"], is_tracked=True)

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "list_channel_posts", channel="chan", days=bad_days)


class TestListAllPosts:
    """S11 — list_all_posts returns from tracked channels only."""

    async def test_list_all_posts_tracked_only(self, app_context: Any) -> None:
        ch_a = await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        ch_b = await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=False
        )
        now = datetime.now(UTC)
        await app_context.repo.upsert_posts(
            ch_a.id, [MessageInfo(telegram_message_id=1, timestamp_utc=now, text="from-a")]
        )
        await app_context.repo.upsert_posts(
            ch_b.id, [MessageInfo(telegram_message_id=10, timestamp_utc=now, text="from-b")]
        )

        result = await _call_tool(
            app_context,
            "list_all_posts",
            start_date="2026-01-01",
            end_date="2030-12-31",
        )
        assert len(result) == 1
        assert result[0]["text"] == "from-a"


class TestMcpToolRegistration:
    """The new public surface must include add_channel_all and the destructive tools."""

    def test_tool_registration_includes_new_tools(self) -> None:
        import package_tgmcpspy.server as server_module

        names = set(server_module.mcp._tool_manager._tools.keys())
        assert "add_channel_all" in names
        assert "add_channel_batch" in names
        assert "remove_all_channels" in names
        assert "trash_all_messages" in names
        assert "sync_dialogs" not in names


class TestRemoveAllChannels:
    """Tests for the remove_all_channels destructive tool."""

    async def test_remove_all_channels_rejects_missing_confirm(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)

        repo_purge = app_context.repo.purge_all_cache
        app_context.repo.purge_all_cache = _fail_purge

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "remove_all_channels")

        app_context.repo.purge_all_cache = repo_purge

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 1

    async def test_remove_all_channels_rejects_false_confirm(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "remove_all_channels", confirm=False)

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 1

    async def test_remove_all_channels_deletes_all_data_on_confirm(
        self, app_context: Any, fake_client: Any
    ) -> None:
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        fake_client.add_channel(telegram_id=2, username="b", title="B")
        ch_a = await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)
        ch_b = await app_context.repo.upsert_channel(fake_client._channels["b"], is_tracked=True)
        await app_context.repo.upsert_posts(ch_a.id, [MessageInfo(1, datetime.now(UTC), "x")])
        await app_context.repo.upsert_posts(ch_b.id, [MessageInfo(2, datetime.now(UTC), "y")])

        result = await _call_tool(app_context, "remove_all_channels", confirm=True)

        assert result == {"posts_deleted": 2, "channels_deleted": 2}
        assert await app_context.repo.list_tracked_channels() == []

    async def test_remove_all_channels_on_empty_cache_returns_zero(self, app_context: Any) -> None:
        result = await _call_tool(app_context, "remove_all_channels", confirm=True)
        assert result == {"posts_deleted": 0, "channels_deleted": 0}

    async def test_remove_all_channels_is_idempotent(self, app_context: Any) -> None:
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )

        first = await _call_tool(app_context, "remove_all_channels", confirm=True)
        second = await _call_tool(app_context, "remove_all_channels", confirm=True)

        assert first == {"posts_deleted": 0, "channels_deleted": 1}
        assert second == {"posts_deleted": 0, "channels_deleted": 0}


class TestTrashAllMessages:
    """Tests for the trash_all_messages destructive tool."""

    async def test_trash_all_messages_rejects_missing_confirm(self, app_context: Any) -> None:
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "trash_all_messages")

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 1

    async def test_trash_all_messages_rejects_false_confirm(self, app_context: Any) -> None:
        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )

        with pytest.raises(ConfigError):
            await _call_tool(app_context, "trash_all_messages", confirm=False)

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 1

    async def test_trash_all_messages_clears_cache_on_confirm(self, app_context: Any) -> None:
        ch = await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        await app_context.repo.upsert_posts(
            ch.id,
            [MessageInfo(1, datetime.now(UTC), "x"), MessageInfo(2, datetime.now(UTC), "y")],
        )

        result = await _call_tool(app_context, "trash_all_messages", confirm=True)

        assert result == {"posts_deleted": 2, "channels_deleted": 1}
        assert await app_context.repo.list_tracked_channels() == []

    async def test_trash_all_messages_resets_update_state(
        self, app_context: Any, fake_client: Any
    ) -> None:
        """A confirmed trash leaves no prior update state for future updates."""
        ch = await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        await app_context.repo.update_channel_stats(ch.id, 100, datetime.now(UTC))

        await _call_tool(app_context, "trash_all_messages", confirm=True)

        # Re-add and inspect; no cached last_message_id should leak through.
        re_added = await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        assert re_added.last_message_id is None


class TestSharedLock:
    """Tests for the shared sequential execution mechanism."""

    async def test_lock_serializes_update_and_reset(self, app_context: Any) -> None:
        """update_channel and a confirmed reset cannot overlap."""
        import asyncio

        from package_tgmcpspy.server import _update_channel

        fake_client = app_context.client
        fake_client.add_channel(telegram_id=1, username="a", title="A")
        await app_context.repo.upsert_channel(fake_client._channels["a"], is_tracked=True)

        # Patch _update_channel to hold the lock for a measurable time. If
        # another tool ran concurrently, it would observe a non-empty state.
        original = _update_channel

        async def slow_update(app: object, identifier: str) -> dict[str, Any]:
            await asyncio.sleep(0.05)
            return await original(app, identifier)  # type: ignore[arg-type]

        import package_tgmcpspy.server as server_module

        server_module._update_channel = slow_update

        try:
            update_task = asyncio.create_task(
                _call_tool(app_context, "update_channel", channel="a")
            )

            # Wait just enough for the update to acquire the lock, then schedule
            # a destructive reset. It must wait until update completes.
            await asyncio.sleep(0.01)
            reset_task = asyncio.create_task(
                _call_tool(app_context, "remove_all_channels", confirm=True)
            )

            update_result, reset_result = await asyncio.gather(update_task, reset_task)
        finally:
            server_module._update_channel = original

        # If the reset had run concurrently, the update's `_update_channel`
        # call would have raced with the channel delete; we verify the reset
        # ran after the update by checking the reset saw zero channels.
        assert reset_result == {"posts_deleted": 0, "channels_deleted": 1}
        # The update also completed successfully.
        assert update_result["fetched"] == 0

    async def test_lock_blocks_overlapping_destructive_calls(self, app_context: Any) -> None:
        """Two concurrent destructive calls do not overlap."""
        import asyncio

        await app_context.repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )

        in_progress = asyncio.Event()
        proceed = asyncio.Event()

        original_repo_purge = app_context.repo.purge_all_cache

        async def gated_purge() -> dict[str, int]:
            in_progress.set()
            await proceed.wait()
            result: dict[str, int] = await original_repo_purge()
            return result

        app_context.repo.purge_all_cache = gated_purge
        try:
            first = asyncio.create_task(
                _call_tool(app_context, "remove_all_channels", confirm=True)
            )
            await in_progress.wait()
            second = asyncio.create_task(
                _call_tool(app_context, "trash_all_messages", confirm=True)
            )
            # Give the second task a chance to attempt and stall on the lock.
            await asyncio.sleep(0.05)
            assert not second.done()
            proceed.set()
            first_result, second_result = await asyncio.gather(first, second)
        finally:
            app_context.repo.purge_all_cache = original_repo_purge

        # First call removed the channel; second call saw zero rows.
        assert first_result == {"posts_deleted": 0, "channels_deleted": 1}
        assert second_result == {"posts_deleted": 0, "channels_deleted": 0}


# --- helpers ---


async def _fail_fetch(*args: object, **kwargs: object) -> Any:
    raise AssertionError("fetch_messages_* must not be called")


async def _fail_purge() -> dict[str, Any]:
    raise AssertionError("purge_all_cache must not be called without confirmation")


def _app_context_with_backfill(
    monkeypatch: pytest.MonkeyPatch,
    app_context: Any,
    *,
    backfill_days: int,
) -> None:
    """Replace the test app context's config with one carrying ``backfill_days``."""
    new_config = replace(app_context.config, backfill_days=backfill_days)
    object.__setattr__(app_context, "config", new_config)
    import package_tgmcpspy.server as server_module

    server_module._app_context = app_context


async def _call_tool(app: Any, tool_name: str, **kwargs: object) -> Any:
    """Call a server tool function by name, injecting the app context."""
    import package_tgmcpspy.server as server_module

    class _FakeRequestContext:
        lifespan_context = app

    class _FakeCtx:
        request_context = _FakeRequestContext()

    ctx = _FakeCtx()

    tool_fn = getattr(server_module, tool_name)
    return await tool_fn(ctx, **kwargs)
