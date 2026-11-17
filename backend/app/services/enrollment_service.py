"""Enrollment rules: the status state machine, duplicate handling, and the weekly-hours guard.

The database already enforces these rules (Database_inital):
  * enrollments_status_check        - status is active | paused | completed | abandoned
  * enrollments_one_open_per_cert   - one open (active or paused) enrollment per certification
  * enrollments_check_total_hours   - open enrollments of one learner total <= 168 hours/week

This service checks them first so learners get a clear 4xx, and still maps the
database errors in case two requests race past the checks.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import enrollments as repo
from app.schemas.enrollment import MAX_WEEKLY_HOURS, EnrollmentCreate, EnrollmentUpdate

OPEN_STATUSES = frozenset({"active", "paused"})

# Allowed status changes. completed and abandoned are final: to study the same
# certification again, the learner creates a new enrollment and the old row stays as history.
TRANSITIONS: dict[str, frozenset[str]] = {
    "active": frozenset({"paused", "completed", "abandoned"}),
    "paused": frozenset({"active", "completed", "abandoned"}),
    "completed": frozenset(),
    "abandoned": frozenset(),
}

# Postgres error codes (SQLSTATE).
_UNIQUE_VIOLATION = "23505"
_FOREIGN_KEY_VIOLATION = "23503"
_CHECK_VIOLATION = "23514"
_RAISE_EXCEPTION = "P0001"  # what enrollments_check_total_hours raises


def can_transition(current: str, new: str) -> bool:
    """True if status may change from current to new. Staying the same is always allowed."""
    return current == new or new in TRANSITIONS.get(current, frozenset())


def _unprocessable(message: str) -> HTTPException:
    # Literal 422: the constant's name differs between Starlette versions.
    return HTTPException(422, message)


def _already_enrolled() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, "You already have an open enrollment for this certification")


def _hours_exceeded(total: Decimal) -> HTTPException:
    return _unprocessable(
        f"Weekly study hours across your open enrollments would be {total}, "
        f"which is more than the {MAX_WEEKLY_HOURS} hours in a week"
    )


def _sqlstate(exc: DBAPIError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


def _http_error_for(exc: DBAPIError) -> HTTPException | None:
    """Map a database rule violation to the HTTP error the contract promises, or None."""
    code = _sqlstate(exc)
    text = str(exc.orig)
    if code == _UNIQUE_VIOLATION and "enrollments_one_open_per_cert" in text:
        return _already_enrolled()
    if code == _RAISE_EXCEPTION and "weekly_study_hours" in text:
        return _unprocessable("Weekly study hours across your open enrollments would exceed 168 hours")
    if code == _CHECK_VIOLATION:
        return _unprocessable("The enrollment values are not allowed")
    if code == _FOREIGN_KEY_VIOLATION:
        return _unprocessable("That certification does not exist")
    return None


async def _check_weekly_hours(
    db: AsyncSession, user_id: int, hours: Decimal | None, exclude_enrollment_id: int | None = None
) -> None:
    if hours is None:
        return
    total = await repo.open_hours_for_user(db, user_id, exclude_enrollment_id) + Decimal(hours)
    if total > MAX_WEEKLY_HOURS:
        raise _hours_exceeded(total)


async def list_certifications(db: AsyncSession) -> list[dict[str, Any]]:
    return await repo.list_active_certifications(db)


async def list_enrollments(db: AsyncSession, user_id: int) -> list[dict[str, Any]]:
    return await repo.list_for_user(db, user_id)


async def create_enrollment(db: AsyncSession, user_id: int, body: EnrollmentCreate) -> dict[str, Any]:
    if await repo.get_active_certification(db, body.certification_id) is None:
        raise _unprocessable("That certification does not exist or is not open for enrollment")

    await _check_weekly_hours(db, user_id, body.weekly_study_hours)

    try:
        new_id = await repo.insert_open_enrollment(
            db,
            user_id=user_id,
            certification_id=body.certification_id,
            goal=body.goal,
            deadline=body.deadline,
            weekly_study_hours=body.weekly_study_hours,
        )
        if new_id is None:
            # ON CONFLICT on enrollments_one_open_per_cert: an open enrollment already exists.
            await db.rollback()
            raise _already_enrolled()
        await db.commit()
    except DBAPIError as exc:
        await db.rollback()
        mapped = _http_error_for(exc)
        if mapped is None:
            raise
        raise mapped from exc

    created = await repo.get_for_user(db, new_id, user_id)
    assert created is not None  # just committed by this user
    return created


async def update_enrollment(
    db: AsyncSession, user_id: int, enrollment_id: int, body: EnrollmentUpdate
) -> dict[str, Any]:
    current = await repo.get_for_user(db, enrollment_id, user_id)
    if current is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enrollment not found")

    # Only fields the client actually sent; an explicit null clears goal/deadline/hours.
    changes: dict[str, Any] = {field: getattr(body, field) for field in body.model_fields_set}
    if "status" in changes and changes["status"] is None:
        raise _unprocessable("status cannot be null")

    if current["status"] not in OPEN_STATUSES:
        raise _unprocessable(f"This enrollment is {current['status']} and can no longer be changed")

    new_status = changes.get("status", current["status"])
    if not can_transition(current["status"], new_status):
        raise _unprocessable(f"Cannot change status from {current['status']} to {new_status}")

    # Only open enrollments count toward the weekly limit.
    if new_status in OPEN_STATUSES:
        hours = changes.get("weekly_study_hours", current["weekly_study_hours"])
        await _check_weekly_hours(db, user_id, hours, exclude_enrollment_id=enrollment_id)

    if changes:
        try:
            await repo.update_enrollment(db, enrollment_id, user_id, changes)
            await db.commit()
        except DBAPIError as exc:
            await db.rollback()
            mapped = _http_error_for(exc)
            if mapped is None:
                raise
            raise mapped from exc

    updated = await repo.get_for_user(db, enrollment_id, user_id)
    assert updated is not None
    return updated
