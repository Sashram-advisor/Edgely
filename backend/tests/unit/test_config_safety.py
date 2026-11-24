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


def test_local_tutor_mount_needs_both_switches() -> None:
    # O4/T5: the offline /local-tutor bridge follows the same two-switch rule.
    assert _settings(app_env="local", enable_local_tutor_mount=True).local_tutor_mount_enabled is True
    assert _settings(app_env="local", enable_local_tutor_mount=False).local_tutor_mount_enabled is False
    assert _settings(app_env="production", enable_local_tutor_mount=True).local_tutor_mount_enabled is False
    assert _settings(app_env="development", enable_local_tutor_mount=True).local_tutor_mount_enabled is False


def test_env_template_defaults_to_production() -> None:
    # T5 / "four things that will quietly break this plan": a copied template
    # must not turn on local-only behaviour.
    from pathlib import Path

    template = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    active = [line.strip() for line in template.splitlines() if line.strip().startswith("APP_ENV=")]
    assert active == ["APP_ENV=production"]


def test_rate_limit_defaults_are_on(monkeypatch) -> None:
    # T4: the tutor is rate-limited unless someone explicitly sets 0.
    monkeypatch.delenv("TUTOR_RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("TUTOR_RATE_LIMIT_PER_DAY", raising=False)
    s = _settings()
    assert s.tutor_rate_limit_per_minute > 0
    assert s.tutor_rate_limit_per_day > 0


def test_legacy_mount_needs_both_switches() -> None:
    assert _settings(app_env="local", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is True
    assert _settings(app_env="local", enable_legacy_tutor_mount=False).legacy_tutor_mount_enabled is False
    assert _settings(app_env="production", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is False
    assert _settings(app_env="development", enable_legacy_tutor_mount=True).legacy_tutor_mount_enabled is False
