"""Shared pytest setup for backend/tests.

Two things live here so test modules do not each reinvent them:

1. Import setup. backend/ goes on sys.path, and dummy settings are set so
   app.core.config, app.core.db and the tutor's own settings can be imported
   without a real backend/.env. No connection is opened by importing.

2. A disposable Postgres database for tests that need real SQL. Set

       EDGELY_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edgely_test

   to an empty database you do not mind tests writing to. Every test that asks
   for ``run_db`` gets its own fresh schema built from Database_inital, which
   is dropped afterwards, so tests cannot see each other's rows. Without the
   variable those tests are skipped, not failed.

   Usage:

       def test_something(run_db):
           rows = run_db(lambda db: some_service.list_things(db))
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path
from typing import Any, TypeVar

import pytest

BACKEND = Path(__file__).resolve().parents[1]
SCHEMA_FILE = BACKEND / "app" / "database" / "migrations" / "Database_inital"

# --------------------------------------------------------------------------
# 1. Import setup
# --------------------------------------------------------------------------

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# setdefault: a real value already in the environment always wins.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")

# test_migrations.py needs psycopg (and a local Postgres) at import time.
# Without psycopg, skip collecting it instead of aborting the whole run.
collect_ignore: list[str] = []
try:
    import psycopg  # noqa: F401
except ImportError:
    collect_ignore.append("integration/test_migrations.py")


# --------------------------------------------------------------------------
# 2. Disposable database
# --------------------------------------------------------------------------

T = TypeVar("T")
RunDb = Callable[[Callable[[Any], Awaitable[T]]], T]


def _plain_url(url: str) -> str:
    """asyncpg.connect wants postgresql://, not the SQLAlchemy driver form."""
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """The disposable database URL, or skip the test when none is configured."""
    url = os.environ.get("EDGELY_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set EDGELY_TEST_DATABASE_URL to run database tests")
    return _plain_url(url)


@pytest.fixture
def db_schema(test_database_url: str) -> Iterator[str]:
    """A fresh schema with the full Database_inital schema applied. Dropped afterwards."""
    import asyncpg

    schema = f"test_{uuid.uuid4().hex[:12]}"

    async def create() -> None:
        conn = await asyncpg.connect(test_database_url)
        try:
            await conn.execute(f'CREATE SCHEMA "{schema}"')
            await conn.execute(f'SET search_path TO "{schema}"')
            await conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def drop() -> None:
        conn = await asyncpg.connect(test_database_url)
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            await conn.close()

    asyncio.run(create())
    try:
        yield schema
    finally:
        asyncio.run(drop())


@pytest.fixture
def run_db(test_database_url: str, db_schema: str) -> Iterator[RunDb]:
    """Run ``fn(session)`` against the test schema and return its result.

    Each call gets a new AsyncSession, the same way each request gets one in
    the app, so commits and rollbacks behave as they do in production.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        test_database_url.replace("postgresql://", "postgresql+asyncpg://", 1),
        # NullPool: every run_db call uses its own event loop, and an asyncpg
        # connection cannot be reused across loops.
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": db_schema}},
    )

    def run(fn: Callable[[Any], Awaitable[T]]) -> T:
        async def go() -> T:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await fn(session)

        return asyncio.run(go())

    try:
        yield run
    finally:
        asyncio.run(engine.dispose())


@pytest.fixture
def seed_sql(test_database_url: str, db_schema: str) -> Callable[[str], None]:
    """Run raw SQL (for example INSERTs of test rows) inside the test schema."""
    import asyncpg

    def run(sql: str) -> None:
        async def go() -> None:
            conn = await asyncpg.connect(test_database_url)
            try:
                await conn.execute(f'SET search_path TO "{db_schema}"')
                await conn.execute(sql)
            finally:
                await conn.close()

        asyncio.run(go())

    return run
