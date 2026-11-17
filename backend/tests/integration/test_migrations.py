import os
import subprocess
from pathlib import Path

import psycopg
import pytest

BACKEND = Path(__file__).resolve().parents[2]
ADMIN_URL = "postgresql://kethanumanarayanan@localhost:5432/postgres"
TEST_DB = "edgely_migtest"


@pytest.fixture
def empty_database():
    admin = psycopg.connect(ADMIN_URL, autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    admin.execute(f'CREATE DATABASE "{TEST_DB}"')
    admin.close()
    url = f"postgresql://kethanumanarayanan@localhost:5432/{TEST_DB}"
    yield url
    admin = psycopg.connect(ADMIN_URL, autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    admin.close()


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    return subprocess.run(
        ["alembic", *args],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def test_upgrade_is_idempotent(empty_database: str) -> None:
    first = _alembic(empty_database, "upgrade", "head")
    second = _alembic(empty_database, "upgrade", "head")

    assert "Running upgrade" in first.stderr
    assert "Running upgrade" not in second.stderr

    with psycopg.connect(empty_database) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert version is not None
        assert version[0] == "4e24c9c49854"
        users = conn.execute("SELECT to_regclass('public.users')").fetchone()
        assert users is not None
        assert users[0] == "users"