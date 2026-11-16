"""SQL for certifications and enrollments.

Plain queries over app.core.db helpers. No business rules live here; the
service decides what is allowed and turns database errors into HTTP errors.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import fetch_all, fetch_one

_ENROLLMENT_COLUMNS = """
    e.id,
    e.certification_id,
    c.name AS certification_name,
    c.slug AS certification_slug,
    e.status,
    e.goal,
    e.deadline,
    e.weekly_study_hours,
    e.created_at
"""

# Columns PATCH may change. Anything else is never written from a request.
UPDATABLE_COLUMNS = ("status", "goal", "deadline", "weekly_study_hours")


async def list_active_certifications(db: AsyncSession) -> list[dict[str, Any]]:
    return await fetch_all(
        db,
        "SELECT id, name, slug, description FROM certifications WHERE is_active ORDER BY name, id",
    )


async def get_active_certification(db: AsyncSession, certification_id: int) -> dict[str, Any] | None:
    return await fetch_one(
        db,
        "SELECT id, name, slug, description FROM certifications WHERE id = :id AND is_active",
        {"id": certification_id},
    )


async def list_for_user(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    return await fetch_all(
        db,
        f"""
        SELECT {_ENROLLMENT_COLUMNS}
        FROM enrollments e
        JOIN certifications c ON c.id = e.certification_id
        WHERE e.user_id = :user_id
        ORDER BY e.created_at DESC, e.id DESC
        """,
        {"user_id": user_id},
    )


async def get_for_user(db: AsyncSession, enrollment_id: int, user_id: int) -> dict[str, Any] | None:
    """One enrollment, only if it belongs to user_id. Someone else's row looks missing."""
    return await fetch_one(
        db,
        f"""
        SELECT {_ENROLLMENT_COLUMNS}
        FROM enrollments e
        JOIN certifications c ON c.id = e.certification_id
        WHERE e.id = :id AND e.user_id = :user_id
        """,
        {"id": enrollment_id, "user_id": user_id},
    )


async def open_hours_for_user(db: AsyncSession, user_id: int, exclude_enrollment_id: int | None = None) -> Decimal:
    """Total weekly_study_hours over the learner's open (active or paused) enrollments."""
    row = await fetch_one(
        db,
        """
        SELECT COALESCE(SUM(weekly_study_hours), 0) AS hours
        FROM enrollments
        WHERE user_id = :user_id
          AND status IN ('active', 'paused')
          AND (CAST(:exclude_id AS BIGINT) IS NULL OR id <> :exclude_id)
        """,
        {"user_id": user_id, "exclude_id": exclude_enrollment_id},
    )
    return Decimal(row["hours"]) if row else Decimal(0)


async def insert_open_enrollment(
    db: AsyncSession,
    *,
    user_id: int,
    certification_id: int,
    goal: str | None,
    deadline: Any,
    weekly_study_hours: Decimal | None,
) -> int | None:
    """Insert an active enrollment. Returns its id, or None if an open one already exists.

    The duplicate check is the partial unique index enrollments_one_open_per_cert,
    used as the ON CONFLICT target, so two concurrent requests cannot both succeed.
    """
    row = await fetch_one(
        db,
        """
        INSERT INTO enrollments (user_id, certification_id, goal, deadline, weekly_study_hours, status)
        VALUES (:user_id, :certification_id, :goal, :deadline, :weekly_study_hours, 'active')
        ON CONFLICT (user_id, certification_id) WHERE status IN ('active', 'paused')
        DO NOTHING
        RETURNING id
        """,
        {
            "user_id": user_id,
            "certification_id": certification_id,
            "goal": goal,
            "deadline": deadline,
            "weekly_study_hours": weekly_study_hours,
        },
    )
    return row["id"] if row else None


async def update_enrollment(db: AsyncSession, enrollment_id: int, user_id: int, changes: dict[str, Any]) -> bool:
    """Apply changes to the user's enrollment. Returns False if no such row is theirs."""
    unknown = set(changes) - set(UPDATABLE_COLUMNS)
    if unknown:
        raise ValueError(f"Not updatable: {sorted(unknown)}")
    if not changes:
        return True

    # Column names come from UPDATABLE_COLUMNS only; values are always bound parameters.
    assignments = ", ".join(f"{column} = :{column}" for column in changes)
    row = await fetch_one(
        db,
        f"UPDATE enrollments SET {assignments} WHERE id = :id AND user_id = :user_id RETURNING id",
        {**changes, "id": enrollment_id, "user_id": user_id},
    )
    return row is not None
