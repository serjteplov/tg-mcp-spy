"""Tests for the SQLite repository layer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine
from sqlalchemy.pool import StaticPool

from package_tgmcpspy.db import Repository, init_schema
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

    async def test_existing_rows_default_to_channel_kind(self) -> None:
        """S27 — pre-existing rows read back with kind='channel' after migration."""
        legacy_metadata = MetaData()
        legacy_channels = Table(
            "channels",
            legacy_metadata,
            Column("id", Integer, primary_key=True),
            Column("telegram_id", Integer, nullable=False, unique=True),
            Column("username", String, nullable=True),
            Column("title", String, nullable=False, default=""),
            Column("is_tracked", Integer, nullable=False, default=0),
            Column("last_message_id", Integer, nullable=True),
            Column("last_fetched_at", String, nullable=True),
        )
        engine = create_engine(
            "sqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        legacy_metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(
                legacy_channels.insert().values(
                    telegram_id=42,
                    username="legacy",
                    title="Legacy",
                    is_tracked=1,
                    last_message_id=99,
                    last_fetched_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
                )
            )

        init_schema(engine)
        repo = Repository(engine)
        loaded = await repo.get_channel_by_telegram_id(42)
        assert loaded is not None
        assert loaded.kind == "channel"
        assert loaded.telegram_id == 42
        assert loaded.title == "Legacy"
        assert loaded.is_tracked is True
        assert loaded.last_message_id == 99

    async def test_upsert_persists_kind_for_each_kind(self, repo: Repository) -> None:
        """R27 — kind round-trips for channels, chats, and users."""
        user = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username=None, title="Alice", kind="user"),
            is_tracked=True,
        )
        chat = await repo.upsert_channel(
            ChannelInfo(telegram_id=2, username=None, title="Family", kind="chat"),
            is_tracked=True,
        )
        channel = await repo.upsert_channel(
            ChannelInfo(telegram_id=3, username="news", title="News", kind="channel"),
            is_tracked=True,
        )

        assert user.kind == "user"
        assert chat.kind == "chat"
        assert channel.kind == "channel"

        tracked = await repo.list_tracked_channels()
        kinds = {ch.telegram_id: ch.kind for ch in tracked}
        assert kinds == {1: "user", 2: "chat", 3: "channel"}


class TestPurgeAllCache:
    """Tests for the transactional full-cache reset."""

    async def test_purge_all_cache_deletes_posts_and_channels_with_counts(
        self, repo: Repository
    ) -> None:
        ch_a = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        ch_b = await repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=True
        )
        await repo.upsert_posts(
            ch_a.id,
            [
                MessageInfo(1, datetime.now(UTC), "x"),
                MessageInfo(2, datetime.now(UTC), "y"),
            ],
        )
        await repo.upsert_posts(ch_b.id, [MessageInfo(10, datetime.now(UTC), "z")])

        result = await repo.purge_all_cache()

        assert result == {"posts_deleted": 3, "channels_deleted": 2}
        assert await repo.list_tracked_channels() == []
        assert (
            await repo.list_channel_posts(
                ch_a.id,
                datetime.now(UTC) - timedelta(days=1),
                datetime.now(UTC) + timedelta(days=1),
            )
            == []
        )
        assert (
            await repo.list_channel_posts(
                ch_b.id,
                datetime.now(UTC) - timedelta(days=1),
                datetime.now(UTC) + timedelta(days=1),
            )
            == []
        )

    async def test_purge_all_cache_on_empty_db_returns_zero_counts(self, repo: Repository) -> None:
        result = await repo.purge_all_cache()
        assert result == {"posts_deleted": 0, "channels_deleted": 0}

    async def test_purge_all_cache_is_idempotent(self, repo: Repository) -> None:
        await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        channel = await repo.get_channel_by_telegram_id(1)
        assert channel is not None
        await repo.upsert_posts(
            channel.id,
            [MessageInfo(1, datetime.now(UTC), "x")],
        )

        first = await repo.purge_all_cache()
        second = await repo.purge_all_cache()

        assert first == {"posts_deleted": 1, "channels_deleted": 1}
        assert second == {"posts_deleted": 0, "channels_deleted": 0}

    async def test_purge_all_cache_untracked_channels(self, repo: Repository) -> None:
        """Untracked channels are also removed; the cache is fully cleared."""
        await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=False
        )
        await repo.upsert_channel(
            ChannelInfo(telegram_id=2, username="b", title="B"), is_tracked=True
        )

        result = await repo.purge_all_cache()
        assert result == {"posts_deleted": 0, "channels_deleted": 2}

    async def test_purge_all_cache_rolls_back_on_failure(self, repo: Repository) -> None:
        """Induced failure mid-transaction must leave all rows intact."""
        from unittest.mock import patch

        from package_tgmcpspy import db as db_module

        ch = await repo.upsert_channel(
            ChannelInfo(telegram_id=1, username="a", title="A"), is_tracked=True
        )
        await repo.upsert_posts(
            ch.id,
            [MessageInfo(1, datetime.now(UTC), "x"), MessageInfo(2, datetime.now(UTC), "y")],
        )

        # Patch the channels delete to raise so the open transaction rolls
        # back. The posts delete has already executed but must be undone.
        with (
            patch.object(
                db_module.channels_table, "delete", side_effect=RuntimeError("induced failure")
            ),
            pytest.raises(RuntimeError),
        ):
            await repo.purge_all_cache()

        tracked = await repo.list_tracked_channels()
        assert len(tracked) == 1
        remaining = await repo.list_channel_posts(
            ch.id,
            datetime.now(UTC) - timedelta(days=1),
            datetime.now(UTC) + timedelta(days=1),
        )
        assert len(remaining) == 2
