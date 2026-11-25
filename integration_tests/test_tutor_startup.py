"""Edgely must keep running when the tutor cannot start, and say why.

T5 (P1) adds: with APP_ENV=production only /tutor is reachable, whatever the
opt-in flags say, and the local-only entry point refuses to start outside local.
Each case runs in a fresh Python process because app.merged_main composes the
app at import time from environment variables.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_edgely_starts_when_tutor_settings_are_missing(tmp_path) -> None:
    empty_env_file = tmp_path / "empty.env"
    empty_env_file.write_text("")

    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPABASE_")}
    env["DATABASE_URL"] = "postgresql://user:pass@127.0.0.1:5432/postgres"
    env["ENV_FILE"] = str(empty_env_file)  # the tutor reads this file, and an empty one has no keys
    env["PYTHONPATH"] = str(ROOT / "backend")

    code = (
        "from fastapi.testclient import TestClient\n"
        "from app.merged_main import app\n"
        "client = TestClient(app)\n"
        "print(client.get('/health/tutor').json()['status'])\n"
        "print(client.post('/tutor/chat', json={'message': 'hi'}).status_code)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60
    )

    assert result.stdout.split() == ["disabled", "404"], result.stderr


def _env(tmp_path, app_env: str, legacy_flag: str, local_flag: str = "false") -> dict[str, str]:
    """Environment for a child process that never reads a developer's real .env."""
    empty_env_file = tmp_path / "empty.env"
    empty_env_file.write_text("")
    env = dict(os.environ)
    env.update(
        {
            "APP_ENV": app_env,
            "ENABLE_LEGACY_TUTOR_MOUNT": legacy_flag,
            "ENABLE_LOCAL_TUTOR_MOUNT": local_flag,
            "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/postgres",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "test-secret-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "GEMINI_API_KEY": "test-gemini-key",
            "ENV_FILE": str(empty_env_file),  # never read a developer's real .env
            "PYTHONPATH": str(ROOT / "backend"),
        }
    )
    return env


def _mounted_paths(tmp_path, app_env: str, legacy_flag: str, local_flag: str = "false") -> list[str]:
    """Start the merged app in a fresh process and report which tutor surfaces exist.

    Prints three booleans: /ai-tutor mounted, /local-tutor/* registered, /tutor/chat registered.
    """
    code = (
        "from app.merged_main import app, tutor_ready, registered_paths\n"
        "assert tutor_ready, 'tutor failed to start'\n"
        "paths = registered_paths()\n"
        "print('/ai-tutor' in paths,"
        " any(p.startswith('/local-tutor') for p in paths),"
        " '/tutor/chat' in paths)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_env(tmp_path, app_env, legacy_flag, local_flag),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.split()


def test_production_never_mounts_the_unauthenticated_tutor(tmp_path) -> None:
    # Even with the opt-in flag on, production keeps /ai-tutor off (P0-3).
    assert _mounted_paths(tmp_path, "production", "true") == ["False", "False", "True"]


def test_production_exposes_only_tutor_even_with_every_flag_on(tmp_path) -> None:
    # T5 "done when": only /tutor is reachable with APP_ENV=production.
    assert _mounted_paths(tmp_path, "production", "true", "true") == ["False", "False", "True"]
    # development is a shared/deployed environment too: same rule.
    assert _mounted_paths(tmp_path, "development", "true", "true") == ["False", "False", "True"]


def test_local_mounts_the_legacy_tutor_only_when_asked(tmp_path) -> None:
    assert _mounted_paths(tmp_path, "local", "false") == ["False", "False", "True"]
    assert _mounted_paths(tmp_path, "local", "true") == ["True", "False", "True"]


def test_local_mounts_the_offline_tutor_only_when_asked(tmp_path) -> None:
    assert _mounted_paths(tmp_path, "local", "false", "true") == ["False", "True", "True"]


def test_local_only_entrypoint_refuses_to_start_outside_local(tmp_path) -> None:
    # T5: the standalone /local-tutor server must not start on a shared machine.
    code = "import app.local_only_main\n"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=_env(tmp_path, "production", "false"),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "only runs with APP_ENV=local" in result.stderr
