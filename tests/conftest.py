"""Shared test fixtures for tg-mcp-spy."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from package_tgmcpspy.config import AppConfig
from package_tgmcpspy.db import Repository, init_schema
from package_tgmcpspy.models import (
    ChannelInfo,
    ChannelNotFoundError,
    ConversationKind,
    MessageInfo,
)


@dataclass(frozen=True)
class AppContext:
    """Mirrors server.AppContext for testing without importing server.py."""

    config: AppConfig
    repo: Repository
    client: FakeTelegramClient
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _memory_engine() -> Engine:
    return create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


@pytest.fixture
def db_engine() -> Engine:
    """In-memory SQLite engine with schema initialized."""
    engine = _memory_engine()
    init_schema(engine)
    return engine


@pytest.fixture
def repo(db_engine: Engine) -> Repository:
    """Async repository backed by an in-memory SQLite database."""
    return Repository(db_engine)


class FakeTelegramClient:
    """Deterministic mock implementing the TelegramClientWrapper interface."""

    def __init__(self) -> None:
        self._channels: dict[str, ChannelInfo] = {}
        self._messages: dict[int, list[MessageInfo]] = {}  # keyed by telegram_id
        self._connect_called = False
        self._disconnect_called = False

    def add_channel(
        self,
        telegram_id: int,
        username: str | None = None,
        title: str = "",
        *,
        kind: ConversationKind = "channel",
    ) -> ChannelInfo:
        """Register a conversation that the fake client knows about."""
        info = ChannelInfo(telegram_id=telegram_id, username=username, title=title, kind=kind)
        if username is not None:
            self._channels[username] = info
        self._channels[str(telegram_id)] = info
        self._messages.setdefault(telegram_id, [])
        return info

    def add_message(
        self,
        telegram_id: int,
        message_id: int,
        text: str = "",
        timestamp: datetime | None = None,
    ) -> MessageInfo:
        """Add a message to a registered channel."""
        ts = timestamp or datetime.now(UTC)
        msg = MessageInfo(telegram_message_id=message_id, timestamp_utc=ts, text=text)
        self._messages.setdefault(telegram_id, []).append(msg)
        return msg

    async def connect(self) -> None:
        self._connect_called = True

    async def disconnect(self) -> None:
        self._disconnect_called = True

    async def get_dialogs(self) -> list[ChannelInfo]:
        seen: set[int] = set()
        result: list[ChannelInfo] = []
        for info in self._channels.values():
            if info.telegram_id not in seen:
                seen.add(info.telegram_id)
                result.append(info)
        return result

    async def resolve_identifier(self, identifier: str) -> ChannelInfo:
        from package_tgmcpspy.models import normalize_identifier

        parsed = normalize_identifier(identifier)
        key = str(parsed)
        if key in self._channels:
            return self._channels[key]
        raise ChannelNotFoundError(f"Channel not found: {identifier!r}")

    async def fetch_messages_since(
        self, channel: ChannelInfo, cutoff: datetime
    ) -> list[MessageInfo]:
        return [m for m in self._messages.get(channel.telegram_id, []) if m.timestamp_utc > cutoff]

    async def fetch_messages_after(self, channel: ChannelInfo, min_id: int) -> list[MessageInfo]:
        return [
            m for m in self._messages.get(channel.telegram_id, []) if m.telegram_message_id > min_id
        ]


@pytest.fixture
def fake_client() -> FakeTelegramClient:
    """Deterministic fake Telegram client."""
    return FakeTelegramClient()


@pytest.fixture
def app_config() -> AppConfig:
    """Test configuration with dummy values."""
    return AppConfig(
        telegram_api_id=12345,
        telegram_api_hash="testhash",
        telegram_session_string="testsession",
        database_path=Path("test.db"),
        post_ttl_days=90,
    )


@pytest.fixture
def app_context(
    repo: Repository,
    fake_client: FakeTelegramClient,
    app_config: AppConfig,
) -> Iterator[AppContext]:
    """Application context wired with fake client and in-memory DB.

    Also binds the server-side ``_app_context`` global so tool helpers can
    resolve the lifespan without spinning up a real FastMCP server.
    """
    import package_tgmcpspy.server as server_module

    context = AppContext(config=app_config, repo=repo, client=fake_client)
    server_module._app_context = context  # type: ignore[assignment]
    try:
        yield context
    finally:
        server_module._app_context = None
