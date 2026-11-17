"""Safety tests for the P0-3 environment switches.

These tests instantiate ``Settings`` directly (no app import), so they do not
need a JWT library or a database. They pin the rule that made the legacy tutor
mount dangerous: one environment variable must not be enough to expose it.
"""

from __future__ import annotations

from app.core.config import Settings

_DB_URL = "postgresql://user:pass@127.0.0.1:5432/postgres"


def _settings(**overrides: object) -> Settings:
    # _env_file=None isolates the test from a developer's real backend/.env.
    return Settings(_env_file=None, database_url=_DB_URL, **overrides)  # type: ignore[arg-type]


def test_default_environment_is_production(monkeypatch) -> None:
    # Settings still reads real environment variables even with _env_file=None,
    # so clear the variable that the test runner may export.
    monkeypatch.delenv("APP_ENV", raising=False)
    assert _settings().app_env == "production"


def test_legacy_mount_is_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_LEGACY_TUTOR_MOUNT", raising=False)
    assert _settings().legacy_tutor_mount_enabled is False


def test_legacy_mount_needs_both_switches() -> None:
    assert _settings(app_env="local", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is True
    assert _settings(app_env="local", enable_legacy_tutor_mount=False).legacy_tutor_mount_enabled is False
    assert _settings(app_env="production", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is False
    assert _settings(app_env="development", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is False
