"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from package_tgmcpspy.config import load_config
from package_tgmcpspy.models import ConfigError


class TestLoadConfig:
    def test_load_config_returns_expected_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.setenv("TGMCPSPY_DB_PATH", "/tmp/test.db")
        monkeypatch.setenv("TGMCPSPY_POST_TTL_DAYS", "30")

        config = load_config()

        assert config.telegram_api_id == 12345
        assert config.telegram_api_hash == "hash"
        assert config.telegram_session_string == "session"
        assert config.database_path == Path("/tmp/test.db")
        assert config.post_ttl_days == 30

    def test_load_config_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.delenv("TGMCPSPY_DB_PATH", raising=False)
        monkeypatch.delenv("TGMCPSPY_POST_TTL_DAYS", raising=False)

        config = load_config()

        assert config.database_path == Path("tgmcpspy.db")
        assert config.post_ttl_days == 90

    def test_load_config_missing_api_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")

        with pytest.raises(ConfigError):
            load_config()

    def test_load_config_invalid_api_id_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "not-an-int")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")

        with pytest.raises(ConfigError):
            load_config()

    def test_load_config_non_positive_ttl_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.setenv("TGMCPSPY_POST_TTL_DAYS", "0")

        with pytest.raises(ConfigError):
            load_config()
