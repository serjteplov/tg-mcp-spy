"""SQLite persistence layer for tg-mcp-spy using SQLAlchemy Core."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    and_,
    func,
    select,
)
from sqlalchemy.engine import Connection, Engine

from package_tgmcpspy.models import Channel, ChannelInfo, MessageInfo, Post

metadata = MetaData()

channels_table = Table(
    "channels",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("telegram_id", Integer, nullable=False, unique=True),
    Column("username", String, nullable=True),
    Column("title", String, nullable=False, default=""),
    Column("is_tracked", Boolean, nullable=False, default=False),
    Column("last_message_id", Integer, nullable=True),
    Column("last_fetched_at", String, nullable=True),
)

posts_table = Table(
    "posts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "channel_id",
        Integer,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("telegram_message_id", Integer, nullable=False),
    Column("text", String, nullable=False, default=""),
    Column("timestamp_utc", String, nullable=False),
    Index("ix_posts_channel_timestamp", "channel_id", "timestamp_utc"),
    Index("ix_posts_timestamp", "timestamp_utc"),
)


def _format_timestamp(dt: datetime) -> str:
    """Store timestamps as UTC ISO-8601 strings."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def _parse_timestamp(value: str) -> datetime:
    """Parse a UTC ISO-8601 string back to a timezone-aware datetime."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _row_to_channel(row: tuple[Any, ...]) -> Channel:
    return Channel(
        id=int(row[0]),
        telegram_id=int(row[1]),
        username=row[2] if row[2] is not None else None,
        title=str(row[3]),
        is_tracked=bool(row[4]),
        last_message_id=int(row[5]) if row[5] is not None else None,
        last_fetched_at=_parse_timestamp(str(row[6])) if row[6] is not None else None,
    )


def _row_to_post(row: tuple[Any, ...]) -> Post:
    return Post(
        id=int(row[0]),
        channel_id=int(row[1]),
        telegram_message_id=int(row[2]),
        text=str(row[3]),
        timestamp_utc=_parse_timestamp(str(row[4])),
    )


class _SyncRepository:
    """Synchronous SQLite repository."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def upsert_channel(
        self,
        info: ChannelInfo,
        *,
        is_tracked: bool = True,
    ) -> Channel:
        """Insert or update a channel and return the resulting record."""
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == info.telegram_id)
            ).first()

            if existing is not None:
                channel_id = int(existing[0])
                conn.execute(
                    channels_table.update()
                    .where(channels_table.c.id == channel_id)
                    .values(
                        username=info.username,
                        title=info.title,
                        is_tracked=is_tracked,
                    )
                )
                return self._get_channel_by_id(conn, channel_id)

            conn.execute(
                channels_table.insert().values(
                    telegram_id=info.telegram_id,
                    username=info.username,
                    title=info.title,
                    is_tracked=is_tracked,
                    last_message_id=None,
                    last_fetched_at=None,
                )
            )
            row = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == info.telegram_id)
            ).first()
            if row is None:
                raise RuntimeError("Inserted channel disappeared immediately")
            return _row_to_channel(tuple(row))

    def _get_channel_by_id(self, conn: Connection, channel_id: int) -> Channel:
        row = conn.execute(select(channels_table).where(channels_table.c.id == channel_id)).first()
        if row is None:
            raise RuntimeError(f"Channel {channel_id} disappeared during upsert")
        return _row_to_channel(tuple(row))

    def list_tracked_channels(self) -> list[Channel]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(channels_table).where(channels_table.c.is_tracked.is_(True))
            ).all()
            return [_row_to_channel(tuple(row)) for row in rows]

    def set_tracked(self, telegram_id: int, tracked: bool) -> Channel | None:
        """Update the tracked flag for a channel and return the record, or None if absent."""
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == telegram_id)
            ).first()
            if existing is None:
                return None

            channel_id = int(existing[0])
            conn.execute(
                channels_table.update()
                .where(channels_table.c.id == channel_id)
                .values(is_tracked=tracked)
            )
            return self._get_channel_by_id(conn, channel_id)

    def get_channel_by_telegram_id(self, telegram_id: int) -> Channel | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == telegram_id)
            ).first()
            return _row_to_channel(tuple(row)) if row is not None else None

    def get_channel_by_username(self, username: str) -> Channel | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(channels_table).where(channels_table.c.username == username)
            ).first()
            return _row_to_channel(tuple(row)) if row is not None else None

    def upsert_posts(self, channel_id: int, messages: Sequence[MessageInfo]) -> int:
        """Insert new messages for a channel; ignore duplicates. Returns inserted count."""
        if not messages:
            return 0

        with self._engine.begin() as conn:
            existing = {
                row[0]
                for row in conn.execute(
                    select(posts_table.c.telegram_message_id).where(
                        posts_table.c.channel_id == channel_id
                    )
                ).all()
            }

            new_messages = [m for m in messages if m.telegram_message_id not in existing]
            if not new_messages:
                return 0

            conn.execute(
                posts_table.insert(),
                [
                    {
                        "channel_id": channel_id,
                        "telegram_message_id": m.telegram_message_id,
                        "text": m.text,
                        "timestamp_utc": _format_timestamp(m.timestamp_utc),
                    }
                    for m in new_messages
                ],
            )
            return len(new_messages)

    def update_channel_stats(
        self,
        channel_id: int,
        last_message_id: int,
        fetched_at: datetime,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                channels_table.update()
                .where(channels_table.c.id == channel_id)
                .values(
                    last_message_id=last_message_id,
                    last_fetched_at=_format_timestamp(fetched_at),
                )
            )

    def get_post(self, channel_id: int, telegram_message_id: int) -> Post | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(posts_table).where(
                    and_(
                        posts_table.c.channel_id == channel_id,
                        posts_table.c.telegram_message_id == telegram_message_id,
                    )
                )
            ).first()
            return _row_to_post(tuple(row)) if row is not None else None

    def list_channel_posts(
        self,
        channel_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Post]:
        start_str = _format_timestamp(start)
        end_str = _format_timestamp(end)
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(posts_table)
                .where(posts_table.c.channel_id == channel_id)
                .where(posts_table.c.timestamp_utc >= start_str)
                .where(posts_table.c.timestamp_utc <= end_str)
                .order_by(posts_table.c.timestamp_utc)
            ).all()
            return [_row_to_post(tuple(row)) for row in rows]

    def list_all_posts(self, start: datetime, end: datetime) -> list[Post]:
        start_str = _format_timestamp(start)
        end_str = _format_timestamp(end)
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(posts_table)
                .where(posts_table.c.timestamp_utc >= start_str)
                .where(posts_table.c.timestamp_utc <= end_str)
                .order_by(posts_table.c.timestamp_utc)
            ).all()
            return [_row_to_post(tuple(row)) for row in rows]

    def purge_old_posts(self, cutoff: datetime) -> int:
        """Delete posts older than the cutoff and return the number deleted."""
        cutoff_str = _format_timestamp(cutoff)
        with self._engine.begin() as conn:
            result = conn.execute(
                posts_table.delete().where(posts_table.c.timestamp_utc < cutoff_str)
            )
            return int(result.rowcount)

    def oldest_post_timestamp(self, channel_id: int) -> datetime | None:
        with self._engine.begin() as conn:
            value = conn.execute(
                select(func.min(posts_table.c.timestamp_utc)).where(
                    posts_table.c.channel_id == channel_id
                )
            ).scalar()
            return _parse_timestamp(str(value)) if value is not None else None


class Repository:
    """Asynchronous facade over the synchronous SQLite repository."""

    def __init__(self, engine: Engine) -> None:
        self._sync = _SyncRepository(engine)

    async def upsert_channel(
        self,
        info: ChannelInfo,
        *,
        is_tracked: bool = True,
    ) -> Channel:
        return await asyncio.to_thread(self._sync.upsert_channel, info, is_tracked=is_tracked)

    async def list_tracked_channels(self) -> list[Channel]:
        return await asyncio.to_thread(self._sync.list_tracked_channels)

    async def set_tracked(self, telegram_id: int, tracked: bool) -> Channel | None:
        return await asyncio.to_thread(self._sync.set_tracked, telegram_id, tracked)

    async def get_channel_by_telegram_id(self, telegram_id: int) -> Channel | None:
        return await asyncio.to_thread(self._sync.get_channel_by_telegram_id, telegram_id)

    async def get_channel_by_username(self, username: str) -> Channel | None:
        return await asyncio.to_thread(self._sync.get_channel_by_username, username)

    async def upsert_posts(
        self,
        channel_id: int,
        messages: Sequence[MessageInfo],
    ) -> int:
        return await asyncio.to_thread(self._sync.upsert_posts, channel_id, messages)

    async def update_channel_stats(
        self,
        channel_id: int,
        last_message_id: int,
        fetched_at: datetime,
    ) -> None:
        await asyncio.to_thread(
            self._sync.update_channel_stats,
            channel_id,
            last_message_id,
            fetched_at,
        )

    async def get_post(self, channel_id: int, telegram_message_id: int) -> Post | None:
        return await asyncio.to_thread(
            self._sync.get_post,
            channel_id,
            telegram_message_id,
        )

    async def list_channel_posts(
        self,
        channel_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Post]:
        return await asyncio.to_thread(
            self._sync.list_channel_posts,
            channel_id,
            start,
            end,
        )

    async def list_all_posts(self, start: datetime, end: datetime) -> list[Post]:
        return await asyncio.to_thread(self._sync.list_all_posts, start, end)

    async def purge_old_posts(self, cutoff: datetime) -> int:
        return await asyncio.to_thread(self._sync.purge_old_posts, cutoff)

    async def oldest_post_timestamp(self, channel_id: int) -> datetime | None:
        return await asyncio.to_thread(self._sync.oldest_post_timestamp, channel_id)


def init_schema(engine: Engine) -> None:
    """Create all tables and indexes if they do not exist."""
    metadata.create_all(engine)
