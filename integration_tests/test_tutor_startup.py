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