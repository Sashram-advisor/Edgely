"""The Alembic chain builds an empty database, and running it again is a no-op.

Needs a Postgres server where the test may create and drop a database.
Point EDGELY_TEST_ADMIN_URL at that server's maintenance database, e.g.

    EDGELY_TEST_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/postgres

The test creates a database called edgely_migtest next to it, migrates it,
and drops it afterwards. Without the variable the test is skipped.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

BACKEND = Path(__file__).resolve().parents[2]
ADMIN_URL = os.environ.get("EDGELY_TEST_ADMIN_URL")
TEST_DB = "edgely_migtest"


def _database_url(admin_url: str, database: str) -> str:
    """Same server and credentials as admin_url, different database name."""
    base, _, _ = admin_url.rpartition("/")
    return f"{base}/{database}"


@pytest.fixture
def empty_database():
    if not ADMIN_URL:
        pytest.skip("set EDGELY_TEST_ADMIN_URL to run the migration test")
    admin = psycopg.connect(ADMIN_URL, autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    admin.execute(f'CREATE DATABASE "{TEST_DB}"')
    admin.close()
    yield _database_url(ADMIN_URL, TEST_DB)
    admin = psycopg.connect(ADMIN_URL, autocommit=True)
    admin.execute(f'DROP DATABASE IF EXISTS "{TEST_DB}" WITH (FORCE)')
    admin.close()


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = url
    return subprocess.run(
        # python -m alembic: works on Windows and in a venv that is not on PATH.
        [sys.executable, "-m", "alembic", *args],
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
