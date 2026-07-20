"""Tests for the FastMCP server tools and helpers.

Importing ``package_tgmcpspy.server`` triggers FastMCP tool registration,
which requires pydantic models that fail outside a real MCP server context.
All server imports are therefore deferred to test methods and helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from package_tgmcpspy.models import ChannelInfo, ChannelNotFoundError, MessageInfo


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


class TestSyncDialogs:
    """S1 — sync_dialogs upserts dialogs as tracked."""

    async def test_sync_dialogs_upserts_tracked(self, app_context: Any, fake_client: Any) -> None:
        fake_client.add_channel(telegram_id=10, username="chan_a", title="A")
        fake_client.add_channel(telegram_id=20, username="chan_b", title="B")

        result = await _call_tool(app_context, "sync_dialogs")
        assert result["synced"] == 2
        assert len(result["channels"]) == 2

        tracked = await app_context.repo.list_tracked_channels()
        assert len(tracked) == 2


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
    """S10, S19 — list_channel_posts inclusive date bounds and full text."""

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


# --- helpers ---


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
