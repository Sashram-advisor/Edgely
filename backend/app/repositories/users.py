"""SQL access for ``users`` and ``learner_profiles``.

This is the only module that writes raw SQL for the identity tables. The
service layer (``services/user_service.py``) owns transactions; the functions
here never commit, so a caller can compose several of them atomically.

Two schema facts drive the design (see ``database/migrations/Database_inital``):

* ``users.external_auth_id`` is UNIQUE -> it is the natural upsert key.
* ``users.email`` is NOT unique -> it must never be used as a conflict target.
* ``learner_profiles.user_id`` is both PK and FK -> provisioning can create it
  with ``ON CONFLICT DO NOTHING`` and stay idempotent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import execute as execute_sql
from app.core.db import fetch_one

# Columns returned to API callers. Keeping the list in one place means the
# route schema and the SQL cannot silently diverge.
_USER_SELECT = """
    SELECT
        u.id,
        u.external_auth_id,
        u.display_name,
        u.email,
        u.role,
        u.created_at,
        p.target_certification_id,
        p.exam_date,
        p.weekly_study_hours,
        p.experience_level
    FROM users AS u
    LEFT JOIN learner_profiles AS p ON p.user_id = u.id
"""

# Columns a PATCH /users/me is allowed to touch on learner_profiles.
# Anything outside this set is rejected by the schema, not interpolated here.
_PROFILE_COLUMNS = ("exam_date", "weekly_study_hours", "experience_level")


async def get_user_by_id(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
    """Return one user joined with the learner profile, or ``None``."""
    return await fetch_one(db, f"{_USER_SELECT} WHERE u.id = :user_id", {"user_id": user_id})


async def get_user_by_auth_id(db: AsyncSession, auth_id: str) -> dict[str, Any] | None:
    """Return the platform user for a Supabase ``sub`` claim, or ``None``."""
    return await fetch_one(
        db,
        f"{_USER_SELECT} WHERE u.external_auth_id = :auth_id",
        {"auth_id": auth_id},
    )


async def upsert_user(
    db: AsyncSession,
    *,
    auth_id: str,
    email: str,
    display_name: str,
) -> int:
    """Create the platform user if needed and return its id.

    On conflict only ``email`` is refreshed. ``display_name`` is left alone so
    a learner who renamed themselves does not get the fallback name back on the
    next login. ``role`` is never taken from the token; new users are learners.
    """

    row = await fetch_one(
        db,
        """
        INSERT INTO users (external_auth_id, email, display_name, role)
        VALUES (:auth_id, :email, :display_name, 'learner')
        ON CONFLICT (external_auth_id)
        DO UPDATE SET email = EXCLUDED.email
        RETURNING id
        """,
        {"auth_id": auth_id, "email": email, "display_name": display_name},
    )
    if row is None:  # pragma: no cover - RETURNING always yields a row here
        raise RuntimeError("users upsert returned no id")
    return int(row["id"])


async def ensure_learner_profile(db: AsyncSession, user_id: int) -> None:
    """Create an empty learner profile; do nothing if it already exists.

    The profile is deliberately created in the same transaction as the user so
    ``GET /users/me`` always returns a complete shape.
    """

    await execute_sql(
        db,
        """
        INSERT INTO learner_profiles (user_id)
        VALUES (:user_id)
        ON CONFLICT (user_id) DO NOTHING
        """,
        {"user_id": user_id},
    )


async def update_display_name(db: AsyncSession, user_id: int, display_name: str) -> int:
    """Rename a user. Returns the affected row count (0 means no such user)."""
    return await execute_sql(
        db,
        "UPDATE users SET display_name = :display_name WHERE id = :user_id",
        {"user_id": user_id, "display_name": display_name},
    )


async def update_learner_profile(
    db: AsyncSession,
    user_id: int,
    values: dict[str, Any],
) -> int:
    """Update the whitelisted profile columns present in ``values``.

    The column names come from ``_PROFILE_COLUMNS`` rather than from user
    input, so the f-string below cannot be used for SQL injection. Values are
    always bound parameters.
    """

    updates = [column for column in _PROFILE_COLUMNS if column in values]
    if not updates:
        return 0

    set_clause = ", ".join(f"{column} = :{column}" for column in updates)
    params = {column: values[column] for column in updates}
    params["user_id"] = user_id

    return await execute_sql(
        db,
        f"UPDATE learner_profiles SET {set_clause} WHERE user_id = :user_id",
        params,
    )
