"""
db.py - Database connection and shared query utilities.

Connects FastAPI to Supabase PostgreSQL using SQLAlchemy 2.0 (async) + asyncpg.
Only the connection string comes from config.py / environment variables;
no credentials are ever hard-coded here.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings  # settings.database_url, settings.db_echo (see config.py)


class Base(DeclarativeBase):
    """Base class for all ORM models in models/ (user.py, quiz.py, ...)."""


def _build_engine() -> AsyncEngine:
    url = settings.database_url
    # Accept the plain Supabase URL and switch it to the asyncpg driver.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)

    return create_async_engine(
        url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # drop dead connections automatically
        pool_recycle=settings.db_pool_recycle_seconds,
        # Supabase's pooler (PgBouncer) does not support prepared statements.
        connect_args={"statement_cache_size": settings.db_statement_cache_size},
    )


engine: AsyncEngine = _build_engine()

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: one session per request.

    Usage:
        @router.get("/dashboard")
        async def dashboard(db: AsyncSession = Depends(get_db)):
            ...
    Commits on success, rolls back on any exception.
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# --------------------------------------------------------------------------
# Shared query utilities (raw SQL helpers for services/ and agents/tools.py)
# Always pass values through `params` - never format them into the SQL string.
# --------------------------------------------------------------------------

async def fetch_all(
    db: AsyncSession, sql: str, params: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    result = await db.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings().all()]


async def fetch_one(
    db: AsyncSession, sql: str, params: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    result = await db.execute(text(sql), params or {})
    row = result.mappings().first()
    return dict(row) if row else None


async def execute(
    db: AsyncSession, sql: str, params: dict[str, Any] | None = None
) -> int:
    """Run INSERT/UPDATE/DELETE. Returns the number of affected rows."""
    result = await db.execute(text(sql), params or {})
    return result.rowcount


# --------------------------------------------------------------------------
# Lifecycle + health
# --------------------------------------------------------------------------

async def check_connection() -> bool:
    """Used by a /health endpoint and at startup."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_db() -> None:
    """Call from FastAPI's lifespan shutdown to release pooled connections."""
    await engine.dispose()