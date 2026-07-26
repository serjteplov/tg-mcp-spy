"""SQLite persistence layer for tg-mcp-spy using SQLAlchemy Core."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    UniqueConstraint,
    and_,
    func,
    select,
)
from sqlalchemy.engine import Connection, Engine

from package_tgmcpspy.models import (
    Channel,
    ChannelInfo,
    ConversationKind,
    MessageInfo,
    Post,
)

metadata = MetaData()

channels_table = Table(
    "channels",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("telegram_id", Integer, nullable=False, unique=True),
    Column("username", String, nullable=True),
    Column("title", String, nullable=False, default=""),
    Column("kind", String, nullable=False, default="channel"),
    Column("is_tracked", Boolean, nullable=False, default=False),
    Column("last_message_id", Integer, nullable=True),
    Column("last_fetched_at", String, nullable=True),
)

channel_groups_table = Table(
    "channel_groups",
    metadata,
    Column(
        "channel_id",
        Integer,
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("group_name", String, nullable=False),
    PrimaryKeyConstraint("channel_id", "group_name"),
    Index("ix_channel_groups_group_name", "group_name"),
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
    Column("username", String, nullable=True),
    Column("display_name", String, nullable=True),
    UniqueConstraint("channel_id", "telegram_message_id"),
    Index("ix_posts_channel_timestamp", "channel_id", "timestamp_utc"),
    Index("ix_posts_timestamp", "timestamp_utc"),
    Index("ix_posts_display_name", "display_name"),
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


def _normalize_groups(value: str) -> tuple[str, ...]:
    """Normalize a space-separated group string."""
    return tuple(sorted(set(value.split())))


def _normalize_group_filter(
    groups: Sequence[str] | str | None,
) -> tuple[str, ...] | None:
    if groups is None:
        return None
    if isinstance(groups, str):
        normalized = _normalize_groups(groups)
        return normalized or None
    normalized = tuple(sorted({group.strip() for group in groups if group.strip()}))
    return normalized or None


def _get_channel_groups(conn: Connection, channel_id: int) -> tuple[str, ...]:
    rows = conn.execute(
        select(channel_groups_table.c.group_name)
        .where(channel_groups_table.c.channel_id == channel_id)
        .order_by(channel_groups_table.c.group_name)
    ).all()
    return tuple(str(row[0]) for row in rows)


def _replace_channel_groups(
    conn: Connection,
    channel_id: int,
    groups: tuple[str, ...],
) -> None:
    conn.execute(
        channel_groups_table.delete().where(channel_groups_table.c.channel_id == channel_id)
    )
    if groups:
        conn.execute(
            channel_groups_table.insert(),
            [{"channel_id": channel_id, "group_name": group} for group in groups],
        )


def _row_to_channel(conn: Connection, row: Any) -> Channel:
    m = row._mapping
    return Channel(
        id=int(m["id"]),
        telegram_id=int(m["telegram_id"]),
        username=m["username"],
        title=str(m["title"]),
        is_tracked=bool(m["is_tracked"]),
        last_message_id=int(m["last_message_id"]) if m["last_message_id"] is not None else None,
        last_fetched_at=(
            _parse_timestamp(str(m["last_fetched_at"]))
            if m["last_fetched_at"] is not None
            else None
        ),
        kind=cast(ConversationKind, str(m["kind"])),
        groups=_get_channel_groups(conn, int(m["id"])),
    )


def _row_to_post(row: Any) -> Post:
    m = row._mapping
    return Post(
        id=int(m["id"]),
        channel_id=int(m["channel_id"]),
        telegram_message_id=int(m["telegram_message_id"]),
        text=str(m["text"]),
        timestamp_utc=_parse_timestamp(str(m["timestamp_utc"])),
        username=m["username"],
        display_name=m["display_name"],
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
        groups: str = "",
    ) -> Channel:
        """Insert or update a channel and return the resulting record."""
        groups_tuple = _normalize_groups(groups) if is_tracked else ()
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == info.telegram_id)
            ).first()

            if existing is not None:
                channel_id = int(existing._mapping["id"])
                conn.execute(
                    channels_table.update()
                    .where(channels_table.c.id == channel_id)
                    .values(
                        username=info.username,
                        title=info.title,
                        is_tracked=is_tracked,
                        kind=info.kind,
                    )
                )
                _replace_channel_groups(conn, channel_id, groups_tuple)
                return self._get_channel_by_id(conn, channel_id)

            conn.execute(
                channels_table.insert().values(
                    telegram_id=info.telegram_id,
                    username=info.username,
                    title=info.title,
                    kind=info.kind,
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
            channel_id = int(row._mapping["id"])
            _replace_channel_groups(conn, channel_id, groups_tuple)
            return self._get_channel_by_id(conn, channel_id)

    def _get_channel_by_id(self, conn: Connection, channel_id: int) -> Channel:
        row = conn.execute(select(channels_table).where(channels_table.c.id == channel_id)).first()
        if row is None:
            raise RuntimeError(f"Channel {channel_id} disappeared during upsert")
        return _row_to_channel(conn, row)

    def list_tracked_channels(
        self,
        groups: Sequence[str] | str | None = None,
    ) -> list[Channel]:
        group_filter = _normalize_group_filter(groups)
        with self._engine.begin() as conn:
            query = select(channels_table).where(channels_table.c.is_tracked.is_(True))
            if group_filter is not None:
                query = query.where(
                    channels_table.c.id.in_(
                        select(channel_groups_table.c.channel_id).where(
                            channel_groups_table.c.group_name.in_(group_filter)
                        )
                    )
                )
            rows = conn.execute(query.order_by(channels_table.c.id)).all()
            return [_row_to_channel(conn, row) for row in rows]

    def get_channel_groups(self, channel_id: int) -> tuple[str, ...]:
        with self._engine.begin() as conn:
            return _get_channel_groups(conn, channel_id)

    def set_channel_groups(self, telegram_id: int, groups: str) -> Channel | None:
        """Replace groups for a tracked channel, or return None when unavailable."""
        groups_tuple = _normalize_groups(groups)
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == telegram_id)
            ).first()
            if existing is None or not bool(existing._mapping["is_tracked"]):
                return None
            channel_id = int(existing._mapping["id"])
            _replace_channel_groups(conn, channel_id, groups_tuple)
            return self._get_channel_by_id(conn, channel_id)

    def set_tracked(self, telegram_id: int, tracked: bool) -> Channel | None:
        """Update the tracked flag for a channel and return the record, or None if absent."""
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(channels_table).where(channels_table.c.telegram_id == telegram_id)
            ).first()
            if existing is None:
                return None

            channel_id = int(existing._mapping["id"])
            if not tracked:
                conn.execute(
                    channel_groups_table.delete().where(
                        channel_groups_table.c.channel_id == channel_id
                    )
                )
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
            return _row_to_channel(conn, row) if row is not None else None

    def get_channel_by_username(self, username: str) -> Channel | None:
        with self._engine.begin() as conn:
            row = conn.execute(
                select(channels_table).where(channels_table.c.username == username)
            ).first()
            return _row_to_channel(conn, row) if row is not None else None

    def list_recent_cached_post_ids(self, channel_id: int, limit: int = 100) -> list[int]:
        """Return newest cached Telegram message IDs in descending order."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        bounded_limit = min(limit, 100)
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(posts_table.c.telegram_message_id)
                .where(posts_table.c.channel_id == channel_id)
                .order_by(posts_table.c.telegram_message_id.desc())
                .limit(bounded_limit)
            ).all()
            return [int(row[0]) for row in rows]

    def upsert_posts(self, channel_id: int, messages: Sequence[MessageInfo]) -> int:
        """Insert new messages for a channel; ignore duplicates. Returns inserted count."""
        if not messages:
            return 0

        with self._engine.begin() as conn:
            existing = {
                row._mapping["telegram_message_id"]
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
                        "username": m.username,
                        "display_name": m.display_name,
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
            return _row_to_post(row) if row is not None else None

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
            return [_row_to_post(row) for row in rows]

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
            return [_row_to_post(row) for row in rows]

    def purge_old_posts(self, cutoff: datetime) -> int:
        """Delete posts older than the cutoff across all channels and return the number deleted."""
        cutoff_str = _format_timestamp(cutoff)
        with self._engine.begin() as conn:
            result = conn.execute(
                posts_table.delete().where(posts_table.c.timestamp_utc < cutoff_str)
            )
            return int(result.rowcount)

    def purge_old_posts_for_channel(self, channel_id: int, cutoff: datetime) -> int:
        """Delete posts older than the cutoff for a specific channel.

        Returns the number of deleted posts.
        """
        cutoff_str = _format_timestamp(cutoff)
        with self._engine.begin() as conn:
            result = conn.execute(
                posts_table.delete().where(
                    and_(
                        posts_table.c.channel_id == channel_id,
                        posts_table.c.timestamp_utc < cutoff_str,
                    )
                )
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

    def purge_all_cache(self) -> dict[str, int]:
        """Delete every cache-owned row in one transaction and return counts.

        Posts are removed first, then channels, so the FK cascade on
        ``posts.channel_id`` is not relied on. The transaction rolls back on
        any failure, leaving the cache unchanged.
        """
        with self._engine.begin() as conn:
            posts_deleted = int(conn.execute(posts_table.delete()).rowcount)
            conn.execute(channel_groups_table.delete())
            channels_deleted = int(conn.execute(channels_table.delete()).rowcount)
        return {
            "posts_deleted": posts_deleted,
            "channels_deleted": channels_deleted,
        }


class Repository:
    """Asynchronous facade over the synchronous SQLite repository."""

    def __init__(self, engine: Engine) -> None:
        self._sync = _SyncRepository(engine)

    async def upsert_channel(
        self,
        info: ChannelInfo,
        *,
        is_tracked: bool = True,
        groups: str = "",
    ) -> Channel:
        return await asyncio.to_thread(
            self._sync.upsert_channel,
            info,
            is_tracked=is_tracked,
            groups=groups,
        )

    async def list_tracked_channels(
        self,
        groups: Sequence[str] | str | None = None,
    ) -> list[Channel]:
        return await asyncio.to_thread(self._sync.list_tracked_channels, groups)

    async def get_channel_groups(self, channel_id: int) -> tuple[str, ...]:
        return await asyncio.to_thread(self._sync.get_channel_groups, channel_id)

    async def set_channel_groups(self, telegram_id: int, groups: str) -> Channel | None:
        return await asyncio.to_thread(self._sync.set_channel_groups, telegram_id, groups)

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

    async def list_recent_cached_post_ids(self, channel_id: int, limit: int = 100) -> list[int]:
        return await asyncio.to_thread(
            self._sync.list_recent_cached_post_ids,
            channel_id,
            limit,
        )

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

    async def purge_old_posts_for_channel(self, channel_id: int, cutoff: datetime) -> int:
        return await asyncio.to_thread(self._sync.purge_old_posts_for_channel, channel_id, cutoff)

    async def oldest_post_timestamp(self, channel_id: int) -> datetime | None:
        return await asyncio.to_thread(self._sync.oldest_post_timestamp, channel_id)

    async def purge_all_cache(self) -> dict[str, int]:
        """Delete every cache-owned row in one transaction and return counts."""
        return await asyncio.to_thread(self._sync.purge_all_cache)


def init_schema(engine: Engine) -> None:
    """Create all tables, indexes, and lightweight schema upgrades.

    Columns added in newer versions (e.g. ``channels.kind``) are appended via
    ``ALTER TABLE`` when the table already exists so existing rows keep working
    without a manual migration step.
    """
    metadata.create_all(engine)
    _upgrade_schema(engine)


def _upgrade_schema(engine: Engine) -> None:
    """Apply lightweight, additive schema upgrades (new columns and indexes)."""
    from sqlalchemy import text

    upgrades: list[tuple[str, str, str]] = [
        ("channels", "kind", "VARCHAR DEFAULT 'channel' NOT NULL"),
        ("posts", "username", "VARCHAR"),
        ("posts", "display_name", "VARCHAR"),
    ]
    index_upgrades: list[tuple[str, str, str]] = [
        ("posts", "ix_posts_display_name", "display_name"),
    ]
    with engine.begin() as conn:
        for table, column, spec in upgrades:
            rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {row[1] for row in rows}
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {spec}"))
        for table, index_name, column in index_upgrades:
            existing_indexes = {
                row[1] for row in conn.execute(text(f"PRAGMA index_list({table})")).fetchall()
            }
            if index_name in existing_indexes:
                continue
            conn.execute(text(f"CREATE INDEX {index_name} ON {table} ({column})"))

        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS channel_groups ("
                "channel_id INTEGER NOT NULL, "
                "group_name VARCHAR NOT NULL, "
                "PRIMARY KEY (channel_id, group_name), "
                "FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE"
                ")"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_channel_groups_group_name "
                "ON channel_groups (group_name)"
            )
        )
