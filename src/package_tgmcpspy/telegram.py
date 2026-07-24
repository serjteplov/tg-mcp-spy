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
from telethon.tl.types import (
    Channel,
    Chat,
    PeerChannel,
    PeerChat,
    PeerUser,
    User,
)

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


def _sender_fields(message: Any) -> tuple[str | None, str | None]:
    """Return ``(username, display_name)`` for a Telethon ``Message``.

    Returns ``(None, None)`` for service messages, deleted-account senders,
    senders that are not a ``User``, and messages with no resolved sender.
    Otherwise ``username`` is the sender's public handle (no leading ``@``)
    and ``display_name`` is ``first_name + last_name`` (trimmed, single
    space) when either name is present, falling back to ``username`` when
    no real name is available.
    """
    if getattr(message, "action", None) is not None:
        return None, None
    sender = getattr(message, "sender", None)
    if sender is None:
        return None, None
    if getattr(sender, "deleted", False):
        return None, None
    if not isinstance(sender, User):
        return None, None
    username = sender.username or None
    first_last = " ".join(
        part for part in (sender.first_name or "", sender.last_name or "") if part
    )
    display_name = first_last or username
    return username, display_name


def _message_to_message_info(message: Any) -> MessageInfo:
    """Build a ``MessageInfo`` from a Telethon ``Message``."""
    username, display_name = _sender_fields(message)
    return MessageInfo(
        telegram_message_id=message.id,
        timestamp_utc=message.date,
        text=message.text or "",
        username=username,
        display_name=display_name,
    )


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
        """Return every conversation from the user's dialogs (channels, chats, users)."""
        channels: list[ChannelInfo] = []
        async for dialog in self._client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, (Channel, Chat, User)):
                channels.append(self._entity_to_channel_info(entity))
        return channels

    @_with_flood_wait
    async def resolve_identifier(self, identifier: str) -> ChannelInfo:
        """Resolve a username or numeric id to a ChannelInfo.

        Accepts any Telegram entity type the user can access: ``User`` (DM),
        ``Chat`` (legacy small group), or ``Channel`` (broadcast/supergroup).
        """
        parsed = normalize_identifier(identifier)
        logger.debug("resolve_identifier: raw=%r normalized=%r", identifier, parsed)
        if isinstance(parsed, int):
            entity = await self._resolve_int_with_cache_warmup(parsed)
        else:
            if not parsed:
                raise ChannelNotFoundError(f"Empty conversation identifier: {identifier!r}")
            entity = await self._client.get_entity(parsed)

        if not isinstance(entity, (Channel, Chat, User)):
            logger.debug(
                "resolve_identifier: unsupported entity type %s for %r",
                type(entity).__name__,
                identifier,
            )
            raise ChannelNotFoundError(
                f"Identifier does not resolve to a channel, chat, or user: {identifier!r}"
            )

        info = self._entity_to_channel_info(entity)
        logger.debug(
            "resolve_identifier: resolved %r -> telegram_id=%d kind=%s "
            "entity_class=%s access_hash_present=%s",
            identifier,
            info.telegram_id,
            info.kind,
            type(entity).__name__,
            getattr(entity, "access_hash", None) is not None,
        )
        return info

    async def _resolve_int_with_cache_warmup(self, parsed: int) -> Channel | Chat | User:
        """Resolve a numeric id, warming Telethon's entity cache on miss.

        Telethon's int-path ``get_entity`` raises
        ``ValueError("Could not find the input entity …")`` when the id is not
        in ``_mb_entity_cache`` or ``MemorySession._entities`` and the
        ``access_hash=0`` fallback to ``users.GetUsers`` / ``channels.GetChannels``
        returns an empty result. The in-memory cache is only populated by
        ``iter_dialogs()`` (via ``client/dialogs.py:61``), so we warm the cache
        by calling ``get_dialogs()`` and retry once before giving up.
        """
        cache_miss_marker = "Could not find the input entity"
        try:
            return await self._client.get_entity(parsed)
        except ValueError as exc:
            if cache_miss_marker not in str(exc):
                raise
            logger.debug(
                "resolve_identifier: cache miss for %d, warming via get_dialogs",
                parsed,
            )
            # `get_dialogs` is already @_with_flood_wait, so its own retries
            # are handled. We call it once and retry get_entity once.
            await self.get_dialogs()
            try:
                return await self._client.get_entity(parsed)
            except ValueError as exc2:
                if cache_miss_marker not in str(exc2):
                    raise
                logger.debug(
                    "resolve_identifier: still unresolvable for %d after warmup",
                    parsed,
                )
                raise ChannelNotFoundError(
                    f"Conversation {parsed} not found in this session. "
                    "If the user/channel is in your dialogs, run add_channel_all "
                    "once to populate the cache; otherwise add by @username."
                ) from exc2

    async def _resolve_entity(self, info: ChannelInfo) -> Channel | Chat | User:
        """Resolve a ChannelInfo back to a Telethon entity by kind.

        NOTE: wrapping ``info.telegram_id`` in a bare ``Peer*`` object drops the
        ``access_hash``. Telethon's ``get_entity(Peer)`` path looks the peer up
        in the in-memory entity cache first and falls back to ``users.getUsers``
        / ``channels.getChannels`` with ``access_hash=0``; if neither the cache
        nor Telegram's ``access_hash=0`` short-circuits resolve the peer, this
        raises ``"Could not find the input entity"``. See Telethon's
        ``get_input_entity`` in ``client/users.py``.
        """
        match info.kind:
            case "user":
                peer: Any = PeerUser(info.telegram_id)
                expected = (User,)
            case "chat":
                peer = PeerChat(info.telegram_id)
                expected = (Chat,)
            case "channel":
                peer = PeerChannel(info.telegram_id)
                expected = (Channel,)
        logger.debug(
            "_resolve_entity: kind=%s telegram_id=%d peer_class=%s",
            info.kind,
            info.telegram_id,
            type(peer).__name__,
        )
        try:
            in_memory_cache = getattr(self._client, "_mb_entity_cache", None)
            if in_memory_cache is not None and hasattr(in_memory_cache, "get"):
                cached = in_memory_cache.get(info.telegram_id)
                logger.debug(
                    "_resolve_entity: in-memory cache lookup for %d -> %s",
                    info.telegram_id,
                    "hit" if cached is not None else "miss",
                )
            session = getattr(self._client, "session", None)
            disk_has = None
            if session is not None and hasattr(session, "get_input_entity"):
                try:
                    session_lookup = session.get_input_entity(peer)
                    disk_has = type(session_lookup).__name__
                except Exception as exc:  # noqa: BLE001 — diagnostic only
                    disk_has = f"miss({type(exc).__name__})"
            logger.debug(
                "_resolve_entity: disk session lookup for %d -> %s",
                info.telegram_id,
                disk_has,
            )
            entity = await self._client.get_entity(peer)
        except Exception as exc:
            logger.debug(
                "_resolve_entity: get_entity(%s(%d)) raised %s: %s",
                type(peer).__name__,
                info.telegram_id,
                type(exc).__name__,
                exc,
            )
            raise
        if not isinstance(entity, expected):
            logger.debug(
                "_resolve_entity: kind mismatch for %d (expected %s, got %s)",
                info.telegram_id,
                expected,
                type(entity).__name__,
            )
            raise ChannelNotFoundError(
                f"Conversation info does not resolve to {info.kind}: {info.telegram_id}"
            )
        logger.debug(
            "_resolve_entity: resolved telegram_id=%d -> %s access_hash_present=%s",
            info.telegram_id,
            type(entity).__name__,
            getattr(entity, "access_hash", None) is not None,
        )
        return entity

    @_with_flood_wait
    async def fetch_messages_since(
        self,
        channel: ChannelInfo,
        cutoff: datetime,
    ) -> list[MessageInfo]:
        """Fetch messages newer than ``cutoff`` for the given conversation."""
        entity = await self._resolve_entity(channel)
        messages = await self._client.get_messages(
            entity,
            offset_date=cutoff,
            reverse=True,
            limit=None,
        )
        return [_message_to_message_info(message) for message in messages]

    @_with_flood_wait
    async def fetch_messages_after(
        self,
        channel: ChannelInfo,
        min_id: int,
    ) -> list[MessageInfo]:
        """Fetch messages with id greater than ``min_id`` for the given conversation."""
        entity = await self._resolve_entity(channel)
        messages = await self._client.get_messages(
            entity,
            min_id=min_id,
            reverse=True,
            limit=None,
        )
        return [_message_to_message_info(message) for message in messages]

    @classmethod
    def _entity_to_channel_info(cls, entity: Channel | Chat | User) -> ChannelInfo:
        """Convert a Telegram entity to a ChannelInfo with the right kind and title."""
        logger.debug(
            "_entity_to_channel_info: entity_class=%s id=%s access_hash_present=%s",
            type(entity).__name__,
            getattr(entity, "id", None),
            getattr(entity, "access_hash", None) is not None,
        )
        if isinstance(entity, Channel):
            return ChannelInfo(
                telegram_id=entity.id,
                username=entity.username if entity.username else None,
                title=entity.title or "",
                kind="channel",
            )
        if isinstance(entity, User):
            full_name = " ".join(
                part for part in (entity.first_name or "", entity.last_name or "") if part
            )
            # Store the bare username (no leading '@') to match Channel.username
            # so callers can look up users and channels with a plain identifier.
            return ChannelInfo(
                telegram_id=entity.id,
                username=entity.username if entity.username else None,
                title=full_name or "",
                kind="user",
            )
        # isinstance(entity, Chat)
        return ChannelInfo(
            telegram_id=entity.id,
            username=None,
            title=entity.title or "",
            kind="chat",
        )
