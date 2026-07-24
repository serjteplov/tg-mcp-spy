"""Tests for configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from package_tgmcpspy.config import AppConfig, load_config
from package_tgmcpspy.models import ConfigError


class TestLoadConfig:
    def test_load_config_returns_expected_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.setenv("TGMCPSPY_DB_PATH", "/tmp/test.db")
        monkeypatch.setenv("TGMCPSPY_POST_TTL_DAYS", "30")
        monkeypatch.setenv("TGMCPSPY_BACKFILL_DAYS", "14")

        config = load_config()

        assert config.telegram_api_id == 12345
        assert config.telegram_api_hash == "hash"
        assert config.telegram_session_string == "session"
        assert config.database_path == Path("/tmp/test.db")
        assert config.post_ttl_days == 30
        assert config.backfill_days == 14

    def test_load_config_uses_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.delenv("TGMCPSPY_DB_PATH", raising=False)
        monkeypatch.delenv("TGMCPSPY_POST_TTL_DAYS", raising=False)
        monkeypatch.delenv("TGMCPSPY_BACKFILL_DAYS", raising=False)

        config = load_config()

        assert config.database_path == Path("tgmcpspy.db")
        assert config.post_ttl_days == 90
        assert config.backfill_days == 7

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


class TestBackfillDaysConfig:
    """Tests for TGMCPSPY_BACKFILL_DAYS parsing and validation."""

    def test_load_config_backfill_default_is_seven(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.delenv("TGMCPSPY_BACKFILL_DAYS", raising=False)

        config = load_config()

        assert config.backfill_days == 7

    def test_load_config_backfill_positive_value_loaded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.setenv("TGMCPSPY_BACKFILL_DAYS", "21")

        config = load_config()

        assert config.backfill_days == 21

    @pytest.mark.parametrize("bad_value", ["0", "-1", "-30", "1.5", "true", "abc", ""])
    def test_load_config_backfill_invalid_raises(
        self, monkeypatch: pytest.MonkeyPatch, bad_value: str
    ) -> None:
        monkeypatch.setenv("TELEGRAM_API_ID", "12345")
        monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
        monkeypatch.setenv("TELEGRAM_SESSION_STRING", "session")
        monkeypatch.setenv("TGMCPSPY_BACKFILL_DAYS", bad_value)

        with pytest.raises(ConfigError):
            load_config()

    def test_app_config_default_backfill_is_seven(self) -> None:
        """Direct construction keeps the documented default of 7 days."""
        config = AppConfig(
            telegram_api_id=1,
            telegram_api_hash="h",
            telegram_session_string="s",
            database_path=Path("db"),
            post_ttl_days=90,
        )
        assert config.backfill_days == 7
