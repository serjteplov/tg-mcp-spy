"""Tests for the Telegram client wrapper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.tl.types import (
    Channel as TlChannel,
)
from telethon.tl.types import (
    Chat as TlChat,
)
from telethon.tl.types import (
    User as TlUser,
)

from package_tgmcpspy.models import ChannelInfo, ChannelNotFoundError, TelegramError


class TestNormalizeIdentifier:
    """Tests for the shared normalize_identifier function (R20)."""

    def test_normalize_identifier_username_returns_str(self) -> None:
        from package_tgmcpspy.models import normalize_identifier

        assert normalize_identifier("  myChannel  ") == "myChannel"

    def test_normalize_identifier_positive_int_returns_int(self) -> None:
        from package_tgmcpspy.models import normalize_identifier

        assert normalize_identifier("12345") == 12345

    def test_normalize_identifier_minus_100_prefix_strips(self) -> None:
        from package_tgmcpspy.models import normalize_identifier

        assert normalize_identifier("-1001234") == 1234

    def test_normalize_identifier_plain_negative(self) -> None:
        from package_tgmcpspy.models import normalize_identifier

        assert normalize_identifier("-42") == 42


class TestResolveIdentifier:
    """Tests for TelegramClientWrapper.resolve_identifier (R20)."""

    async def test_resolve_by_username(self) -> None:
        wrapper = _make_wrapper()
        entity = _make_channel_entity(telegram_id=100, username="testchan", title="Test")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("testchan")
        assert info.telegram_id == 100
        assert info.username == "testchan"

    async def test_resolve_by_numeric_id(self) -> None:
        wrapper = _make_wrapper()
        entity = _make_channel_entity(telegram_id=200, username=None, title="IDChan")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("200")
        assert info.telegram_id == 200

    async def test_resolve_negative_100_id(self) -> None:
        wrapper = _make_wrapper()
        entity = _make_channel_entity(telegram_id=300, username=None, title="NegChan")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("-100300")
        assert info.telegram_id == 300

    async def test_resolve_non_channel_raises(self) -> None:
        wrapper = _make_wrapper()
        wrapper._client.get_entity = AsyncMock(return_value="not_a_channel")

        with pytest.raises(ChannelNotFoundError):
            await wrapper.resolve_identifier("bogus")

    async def test_resolve_user_entity_returns_kind_user(self) -> None:
        """S22 — numeric user id resolves to a User entity with kind='user'."""
        wrapper = _make_wrapper()
        entity = _make_user_entity(telegram_id=6199205118, first_name="Alice", username="alice")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("6199205118")
        assert info.telegram_id == 6199205118
        assert info.title == "Alice"
        assert info.username == "alice"
        assert info.kind == "user"

    async def test_resolve_user_entity_full_name(self) -> None:
        wrapper = _make_wrapper()
        entity = _make_user_entity(
            telegram_id=1, first_name="Alice", last_name="Smith", username=None
        )
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("1")
        assert info.title == "Alice Smith"
        assert info.username is None
        assert info.kind == "user"

    async def test_resolve_chat_entity_returns_kind_chat(self) -> None:
        """S23 — numeric legacy chat id resolves to a Chat entity with kind='chat'."""
        wrapper = _make_wrapper()
        entity = _make_chat_entity(telegram_id=12345, title="Family")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("12345")
        assert info.telegram_id == 12345
        assert info.title == "Family"
        assert info.username is None
        assert info.kind == "chat"

    async def test_resolve_supergroup_returns_kind_channel(self) -> None:
        """S24 — supergroup channel resolves as kind='channel'."""
        wrapper = _make_wrapper()
        entity = _make_supergroup_entity(telegram_id=200, title="Supergroup")
        wrapper._client.get_entity = AsyncMock(return_value=entity)

        info = await wrapper.resolve_identifier("200")
        assert info.telegram_id == 200
        assert info.title == "Supergroup"
        assert info.kind == "channel"

    async def test_get_dialogs_includes_dms_and_chats(self) -> None:
        """M4 — iter_dialogs returns users and chats, not just broadcast channels."""
        wrapper = _make_wrapper()
        user = _make_user_entity(telegram_id=10, first_name="Bob")
        chat = _make_chat_entity(telegram_id=20, title="Group")
        chan = _make_channel_entity(telegram_id=30, title="News")

        async def fake_iter_dialogs() -> Any:
            for entity in (user, chat, chan):
                yield type("Dialog", (), {"entity": entity})()

        wrapper._client.iter_dialogs = fake_iter_dialogs

        infos = await wrapper.get_dialogs()
        kinds = {info.telegram_id: info.kind for info in infos}
        assert kinds == {10: "user", 20: "chat", 30: "channel"}

    async def test_resolve_entity_dispatches_by_kind(self) -> None:
        """M3 — _resolve_entity uses PeerUser/PeerChat/PeerChannel by kind."""
        from telethon.tl.types import PeerChat, PeerUser

        wrapper = _make_wrapper()
        user_entity = _make_user_entity(telegram_id=11, first_name="Carol")
        chat_entity = _make_chat_entity(telegram_id=22, title="Group")
        chan_entity = _make_channel_entity(telegram_id=33, title="Chan")

        async def fake_get_entity(peer: Any) -> Any:
            if isinstance(peer, PeerUser):
                return user_entity
            if isinstance(peer, PeerChat):
                return chat_entity
            return chan_entity

        wrapper._client.get_entity = fake_get_entity

        user_info = ChannelInfo(telegram_id=11, username=None, title="Carol", kind="user")
        chat_info = ChannelInfo(telegram_id=22, username=None, title="Group", kind="chat")
        chan_info = ChannelInfo(telegram_id=33, username=None, title="Chan", kind="channel")

        for info, expected in (
            (user_info, user_entity),
            (chat_info, chat_entity),
            (chan_info, chan_entity),
        ):
            assert (await wrapper._resolve_entity(info)) is expected


class TestFetchMessages:
    """Tests for fetch_messages_since and fetch_messages_after (R9–R10)."""

    async def test_fetch_messages_since_returns_after_cutoff(self) -> None:
        wrapper = _make_wrapper()
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=7)

        msg_new = MagicMock()
        msg_new.id = 2
        msg_new.date = now
        msg_new.text = "new"

        entity = _make_channel_entity(telegram_id=100, username="test", title="Test")
        wrapper._client.get_entity = AsyncMock(return_value=entity)
        wrapper._client.get_messages = AsyncMock(return_value=[msg_new])

        info = ChannelInfo(telegram_id=100, username="test", title="Test")
        messages = await wrapper.fetch_messages_since(info, cutoff)
        assert len(messages) == 1
        assert messages[0].telegram_message_id == 2

    async def test_fetch_messages_after_returns_newer(self) -> None:
        wrapper = _make_wrapper()

        msg = MagicMock()
        msg.id = 11
        msg.date = datetime.now(UTC)
        msg.text = "newer"

        entity = _make_channel_entity(telegram_id=100, username="test", title="Test")
        wrapper._client.get_entity = AsyncMock(return_value=entity)
        wrapper._client.get_messages = AsyncMock(return_value=[msg])

        info = ChannelInfo(telegram_id=100, username="test", title="Test")
        messages = await wrapper.fetch_messages_after(info, min_id=10)
        assert len(messages) == 1
        assert messages[0].telegram_message_id == 11


class TestFloodWaitRetry:
    """Tests for _with_flood_wait retry decorator (S14)."""

    async def test_flood_wait_retries_and_succeeds(self) -> None:
        from telethon.errors import FloodWaitError

        wrapper = _make_wrapper()
        entity = _make_channel_entity(telegram_id=100, username="test", title="Test")

        call_count = 0

        async def fake_get_entity(*args: object, **kwargs: object) -> TlChannel:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise FloodWaitError(request=MagicMock(), capture=0)
            return entity

        wrapper._client.get_entity = fake_get_entity

        info = await wrapper.resolve_identifier("test")
        assert info.telegram_id == 100
        assert call_count == 3

    async def test_flood_wait_exhausted_raises_telegram_error(self) -> None:
        from telethon.errors import FloodWaitError

        wrapper = _make_wrapper()

        async def always_flood(*args: object, **kwargs: object) -> None:
            raise FloodWaitError(request=MagicMock(), capture=0)

        wrapper._client.get_entity = always_flood

        with pytest.raises(TelegramError, match="rate limit exceeded"):
            await wrapper.resolve_identifier("test")


# --- helpers ---


def _make_wrapper() -> Any:
    """Create a TelegramClientWrapper with a mocked Telethon client (no real connection)."""
    from package_tgmcpspy.config import AppConfig
    from package_tgmcpspy.telegram import TelegramClientWrapper

    config = AppConfig(
        telegram_api_id=1,
        telegram_api_hash="hash",
        telegram_session_string="session",
        database_path=Path("test.db"),
        post_ttl_days=90,
    )
    mock_telethon_client = MagicMock()
    mock_telethon_client.get_entity = AsyncMock()
    mock_telethon_client.get_messages = AsyncMock()
    with (
        patch("package_tgmcpspy.telegram.TelegramClient", return_value=mock_telethon_client),
        patch("package_tgmcpspy.telegram.StringSession", return_value=MagicMock()),
    ):
        wrapper = TelegramClientWrapper(config)
    return wrapper


def _make_channel_entity(
    telegram_id: int = 1,
    username: str | None = None,
    title: str = "Test",
) -> TlChannel:
    """Create a real Telethon Channel entity for isinstance checks."""
    return TlChannel(
        id=telegram_id,
        title=title,
        username=username,
        photo=None,
        date=datetime.now(UTC),
        broadcast=True,
    )


def _make_supergroup_entity(
    telegram_id: int = 1,
    title: str = "Supergroup",
) -> TlChannel:
    """Create a Telethon Channel entity representing a supergroup (megagroup)."""
    return TlChannel(
        id=telegram_id,
        title=title,
        username=None,
        photo=None,
        date=datetime.now(UTC),
        broadcast=False,
        megagroup=True,
    )


def _make_user_entity(
    telegram_id: int,
    first_name: str = "User",
    last_name: str | None = None,
    username: str | None = None,
) -> TlUser:
    """Create a real Telethon User entity for isinstance checks."""
    return TlUser(
        id=telegram_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
    )


def _make_chat_entity(telegram_id: int, title: str = "Chat") -> TlChat:
    """Create a real Telethon Chat entity (legacy small group) for isinstance checks."""
    return TlChat(
        id=telegram_id,
        title=title,
        photo=None,
        date=datetime.now(UTC),
        participants_count=0,
        version=0,
    )
