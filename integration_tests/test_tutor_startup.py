"""Edgely must keep running when the tutor cannot start, and say why."""

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

def _mounted_paths(tmp_path, app_env: str, legacy_flag: str) -> list[str]:
    """Start the merged app in a fresh process and report whether /ai-tutor is mounted."""
    empty_env_file = tmp_path / "empty.env"
    empty_env_file.write_text("")

    env = dict(os.environ)
    env.update(
        {
            "APP_ENV": app_env,
            "ENABLE_LEGACY_TUTOR_MOUNT": legacy_flag,
            "DATABASE_URL": "postgresql://user:pass@127.0.0.1:5432/postgres",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "test-secret-key",
            "ANTHROPIC_API_KEY": "test-anthropic-key",
            "GEMINI_API_KEY": "test-gemini-key",
            "ENV_FILE": str(empty_env_file),  # never read a developer's real .env
            "PYTHONPATH": str(ROOT / "backend"),
        }
    )
    code = (
        "from app.merged_main import app, tutor_ready\n"
        "assert tutor_ready, 'tutor failed to start'\n"
        "paths = {getattr(r, 'path', '') for r in app.routes}\n"
        "print('/ai-tutor' in paths, '/tutor/chat' in app.openapi()['paths'])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.split()


def test_production_never_mounts_the_unauthenticated_tutor(tmp_path) -> None:
    # Even with the opt-in flag on, production keeps /ai-tutor off (P0-3).
    assert _mounted_paths(tmp_path, "production", "true") == ["False", "True"]


def test_local_mounts_the_legacy_tutor_only_when_asked(tmp_path) -> None:
    assert _mounted_paths(tmp_path, "local", "false") == ["False", "True"]
    assert _mounted_paths(tmp_path, "local", "true") == ["True", "True"]
