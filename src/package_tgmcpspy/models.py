"""Domain models and exceptions for tg-mcp-spy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def normalize_identifier(identifier: str) -> int | str:
    """Normalize a channel identifier to a telegram_id (int) or username (str).

    Numeric identifiers (including ``-100...``) are converted to a positive
    telegram_id.  The ``-100`` prefix used by Telegram for channel/supergroup
    peer IDs is stripped so that ``-1001234`` resolves to ``1234``.
    Non-numeric identifiers are returned as stripped strings.
    """
    cleaned = identifier.strip()
    # Strip the -100 channel/supergroup prefix used by Telegram peer IDs
    if cleaned.startswith("-100") and cleaned[4:].isdigit():
        return int(cleaned[4:])
    numeric = cleaned.lstrip("-")
    if numeric.isdigit():
        return int(numeric)
    return cleaned


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


class ChannelNotFoundError(Exception):
    """Raised when a channel identifier cannot be resolved."""


class TelegramError(Exception):
    """Raised when a Telegram operation fails."""


@dataclass(frozen=True)
class ChannelInfo:
    """Lightweight information about a Telegram channel."""

    telegram_id: int
    username: str | None
    title: str


@dataclass(frozen=True)
class MessageInfo:
    """Lightweight information about a Telegram message."""

    telegram_message_id: int
    timestamp_utc: datetime
    text: str


@dataclass(frozen=True)
class Channel:
    """A cached Telegram channel record."""

    id: int
    telegram_id: int
    username: str | None
    title: str
    is_tracked: bool
    last_message_id: int | None
    last_fetched_at: datetime | None


@dataclass(frozen=True)
class Post:
    """A cached Telegram post."""

    id: int
    channel_id: int
    telegram_message_id: int
    text: str
    timestamp_utc: datetime
