"""Configuration loading and validation for tg-mcp-spy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from package_tgmcpspy.models import ConfigError


@dataclass(frozen=True)
class AppConfig:
    """Application configuration loaded from environment variables."""

    telegram_api_id: int
    telegram_api_hash: str
    telegram_session_string: str
    database_path: Path
    post_ttl_days: int


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Environment variable {name} is required.")
    return value


def _positive_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(
            f"Environment variable {name} must be an integer, got {value!r}."
        ) from exc
    if parsed <= 0:
        raise ConfigError(f"Environment variable {name} must be positive, got {parsed}.")
    return parsed


def load_config() -> AppConfig:
    """Load and validate configuration from environment variables."""
    api_id = _positive_int("TELEGRAM_API_ID", _require("TELEGRAM_API_ID"))
    api_hash = _require("TELEGRAM_API_HASH")
    session_string = _require("TELEGRAM_SESSION_STRING")

    db_path = Path(os.environ.get("TGMCPSPY_DB_PATH", "tgmcpspy.db"))

    ttl_raw = os.environ.get("TGMCPSPY_POST_TTL_DAYS", "90")
    ttl_days = _positive_int("TGMCPSPY_POST_TTL_DAYS", ttl_raw)

    return AppConfig(
        telegram_api_id=api_id,
        telegram_api_hash=api_hash,
        telegram_session_string=session_string,
        database_path=db_path,
        post_ttl_days=ttl_days,
    )
