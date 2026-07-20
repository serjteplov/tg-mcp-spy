"""Tests for the SQLite repository layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from package_tgmcpspy.db import Repository
from package_tgmcpspy.models import ChannelInfo, MessageInfo


class TestRepository:
    async def test_upsert_channel_inserts_and_updates(self, repo: Repository) -> None:
        info = ChannelInfo(telegram_id=1, username="test", title="Test")
        channel = await repo.upsert_channel(info, is_tracked=True)
        assert channel.telegram_id == 1
        assert channel.is_tracked is True

        updated = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="test", title="Updated"),
            is_tracked=True,
        )
        assert updated.title == "Updated"
        assert updated.id == channel.id

    async def test_list_tracked_channels_filters_untracked(self, repo: Repository) -> None:
        await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        await repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=False
        )

        tracked = await repo.list_tracked_channels()
        assert len(tracked) == 1
        assert tracked[0].telegram_id == 1

    async def test_set_tracked_updates_flag(self, repo: Repository) -> None:
        await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        updated = await repo.set_tracked(1, False)
        assert updated is not None
        assert updated.is_tracked is False

    async def test_upsert_posts_ignores_duplicates(self, repo: Repository) -> None:
        channel = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        messages = [
            MessageInfo(telegram_message_id=10, timestamp_utc=datetime.now(UTC), text="hello"),
        ]
        inserted = await repo.upsert_posts(channel.id, messages)
        assert inserted == 1

        inserted_again = await repo.upsert_posts(channel.id, messages)
        assert inserted_again == 0

    async def test_list_channel_posts_inclusive_range(self, repo: Repository) -> None:
        channel = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        base = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)
        messages = [
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
        ]
        await repo.upsert_posts(channel.id, messages)

        posts = await repo.list_channel_posts(
            channel.id,
            datetime(2026, 7, 15, tzinfo=UTC),
            datetime(2026, 7, 16, 23, 59, 59, tzinfo=UTC),
        )
        assert len(posts) == 2
        assert {post.telegram_message_id for post in posts} == {1, 2}

    async def test_purge_old_posts(self, repo: Repository) -> None:
        channel = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        old = MessageInfo(
            telegram_message_id=1,
            timestamp_utc=datetime.now(UTC) - timedelta(days=100),
            text="old",
        )
        new = MessageInfo(
            telegram_message_id=2,
            timestamp_utc=datetime.now(UTC),
            text="new",
        )
        await repo.upsert_posts(channel.id, [old, new])

        deleted = await repo.purge_old_posts(datetime.now(UTC) - timedelta(days=90))
        assert deleted == 1

        remaining = await repo.list_channel_posts(
            channel.id,
            datetime.now(UTC) - timedelta(days=1),
            datetime.now(UTC) + timedelta(days=1),
        )
        assert len(remaining) == 1
        assert remaining[0].telegram_message_id == 2

    async def test_purge_old_posts_for_channel_scoped(self, repo: Repository) -> None:
        ch_a = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        ch_b = await repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=True
        )
        old_ts = datetime.now(UTC) - timedelta(days=100)
        new_ts = datetime.now(UTC)
        await repo.upsert_posts(ch_a.id, [MessageInfo(1, old_ts, "old-a")])
        await repo.upsert_posts(ch_a.id, [MessageInfo(2, new_ts, "new-a")])
        await repo.upsert_posts(ch_b.id, [MessageInfo(10, old_ts, "old-b")])

        deleted = await repo.purge_old_posts_for_channel(
            ch_a.id, datetime.now(UTC) - timedelta(days=90)
        )
        assert deleted == 1

        # ch_b's old post is untouched
        ch_b_posts = await repo.list_channel_posts(
            ch_b.id, datetime.now(UTC) - timedelta(days=200), datetime.now(UTC)
        )
        assert len(ch_b_posts) == 1
