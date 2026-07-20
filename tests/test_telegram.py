"""Tests for the Telegram client wrapper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.tl.types import Channel as TlChannel

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
