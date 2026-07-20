"""Telegram client wrapper for tg-mcp-spy."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.types import Channel, PeerChannel

from package_tgmcpspy.config import AppConfig
from package_tgmcpspy.models import (
    ChannelInfo,
    ChannelNotFoundError,
    ConfigError,
    MessageInfo,
    TelegramError,
    normalize_identifier,
)

logger = logging.getLogger(__name__)


def _with_flood_wait[T](
    func: Callable[..., Awaitable[T]],
) -> Callable[..., Awaitable[T]]:
    """Retry an async call on FloodWaitError up to 3 times with a capped sleep."""

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        last_error: FloodWaitError | None = None
        for attempt in range(4):  # initial attempt + 3 retries
            try:
                return await func(*args, **kwargs)
            except FloodWaitError as exc:
                last_error = exc
                sleep_seconds = min(exc.seconds, 60)
                logger.warning(
                    "Telegram rate limit hit, sleeping %d seconds (attempt %d)",
                    sleep_seconds,
                    attempt + 1,
                )
                await asyncio.sleep(sleep_seconds)

        raise TelegramError(
            f"Telegram rate limit exceeded after retries: {last_error}"
        ) from last_error

    return wrapper


class TelegramClientWrapper:
    """Thin wrapper around Telethon's TelegramClient."""

    def __init__(self, config: AppConfig) -> None:
        self._client = TelegramClient(
            StringSession(config.telegram_session_string),
            config.telegram_api_id,
            config.telegram_api_hash,
        )

    async def connect(self) -> None:
        """Connect and verify the session is authorized."""
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise ConfigError("Telegram session is not authorized.")

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        await self._client.disconnect()

    @_with_flood_wait
    async def get_dialogs(self) -> list[ChannelInfo]:
        """Return broadcast channels from the user's dialogs."""
        channels: list[ChannelInfo] = []
        async for dialog in self._client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, Channel) and entity.broadcast:
                channels.append(self._entity_to_channel_info(entity))
        return channels

    @_with_flood_wait
    async def resolve_identifier(self, identifier: str) -> ChannelInfo:
        """Resolve a username or numeric channel id to a ChannelInfo."""
        parsed = normalize_identifier(identifier)
        if isinstance(parsed, int):
            entity = await self._client.get_entity(PeerChannel(parsed))
        else:
            if not parsed:
                raise ChannelNotFoundError(f"Empty channel identifier: {identifier!r}")
            entity = await self._client.get_entity(parsed)

        if not isinstance(entity, Channel):
            raise ChannelNotFoundError(f"Identifier does not resolve to a channel: {identifier!r}")

        return self._entity_to_channel_info(entity)

    async def _resolve_entity(self, info: ChannelInfo) -> Channel:
        """Resolve a ChannelInfo back to a Telethon Channel entity."""
        entity = await self._client.get_entity(PeerChannel(info.telegram_id))
        if not isinstance(entity, Channel):
            raise ChannelNotFoundError(
                f"Channel info does not resolve to a channel: {info.telegram_id}"
            )
        return entity

    @_with_flood_wait
    async def fetch_messages_since(
        self,
        channel: ChannelInfo,
        cutoff: datetime,
    ) -> list[MessageInfo]:
        """Fetch messages newer than ``cutoff`` for the given channel."""
        entity = await self._resolve_entity(channel)
        messages = await self._client.get_messages(
            entity,
            offset_date=cutoff,
            reverse=True,
            limit=None,
        )
        return [
            MessageInfo(
                telegram_message_id=message.id,
                timestamp_utc=message.date,
                text=message.text or "",
            )
            for message in messages
        ]

    @_with_flood_wait
    async def fetch_messages_after(
        self,
        channel: ChannelInfo,
        min_id: int,
    ) -> list[MessageInfo]:
        """Fetch messages with id greater than ``min_id`` for the given channel."""
        entity = await self._resolve_entity(channel)
        messages = await self._client.get_messages(
            entity,
            min_id=min_id,
            reverse=True,
            limit=None,
        )
        return [
            MessageInfo(
                telegram_message_id=message.id,
                timestamp_utc=message.date,
                text=message.text or "",
            )
            for message in messages
        ]

    @staticmethod
    def _entity_to_channel_info(entity: Channel) -> ChannelInfo:
        username = entity.username if entity.username else None
        return ChannelInfo(
            telegram_id=entity.id,
            username=username,
            title=entity.title or "",
        )
