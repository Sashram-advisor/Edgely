"""Business rules for platform users.

Responsibilities
----------------
* Turn a verified Supabase identity into a ``users`` row (provisioning).
* Keep ``users`` and ``learner_profiles`` consistent: both rows are created in
  one transaction.
* Apply ``PATCH /users/me`` updates to the right table.

Transaction policy
------------------
The service owns the unit of work. Repositories only execute statements; this
module commits once at the end and rolls back on any failure. That matters for
provisioning: a crash between the two INSERTs must not leave a user without a
profile.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import users as users_repo
from app.schemas.user import UserUpdate

# Supabase can return a token without an email (for example, phone-only sign
# ups). ``users.email`` is NOT NULL, so a deterministic placeholder is stored
# instead of failing the request. The domain is reserved and cannot collide
# with a real address.
_FALLBACK_EMAIL_DOMAIN = "unknown.invalid"


def _fallback_email(auth_id: str) -> str:
    """Build a stable placeholder email for logins that do not carry one."""
    return f"{auth_id}@{_FALLBACK_EMAIL_DOMAIN}"


def _fallback_display_name(email: str) -> str:
    """Use the local part of the email as a friendly default name."""
    local_part = email.split("@", 1)[0].strip()
    return local_part or "Learner"


async def provision_user(
    db: AsyncSession,
    auth_id: str,
    email: str | None = None,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Create the platform user on first login, or return the existing one.

    Idempotent by contract: calling it twice with the same ``auth_id`` returns
    the same row and does not reset a custom ``display_name``.

    Args:
        db: request-scoped session.
        auth_id: the Supabase ``sub`` claim (``users.external_auth_id``).
        email: optional email from the token; a placeholder is used when absent.
        display_name: optional name from the token; the email local part is
            used when absent.

    Returns:
        The joined user/profile row.

    Raises:
        Exception: any database error is re-raised after a rollback.
    """

    token_email = (email or "").strip()
    clean_email = token_email or _fallback_email(auth_id)
    clean_name = (display_name or "").strip() or _fallback_display_name(clean_email)

    try:
        user_id = await users_repo.upsert_user(
            db,
            auth_id=auth_id,
            email=clean_email,
            display_name=clean_name,
            # Only a real email from the token may overwrite the stored one.
            refresh_email=bool(token_email),
        )
        # Same transaction: a user is never visible without a learner profile.
        await users_repo.ensure_learner_profile(db, user_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    user = await users_repo.get_user_by_id(db, user_id)
    if user is None:  # pragma: no cover - the row was just written
        raise RuntimeError(f"provisioned user {user_id} cannot be read back")
    return user


async def get_user(db: AsyncSession, user_id: int) -> dict[str, Any] | None:
    """Return the joined user row, or ``None`` when it does not exist."""
    return await users_repo.get_user_by_id(db, user_id)


async def update_user(
    db: AsyncSession,
    user_id: int,
    update: UserUpdate,
) -> dict[str, Any] | None:
    """Apply a partial update and return the refreshed row.

    ``exclude_unset`` is important: only fields the client actually sent are
    written. That is also what lets an explicit ``null`` clear ``exam_date``
    while an omitted ``exam_date`` leaves it untouched.
    """

    fields = update.model_dump(exclude_unset=True)
    if not fields:
        # An empty PATCH is a no-op rather than an error; it is useful for
        # clients that retry without tracking which fields changed.
        return await users_repo.get_user_by_id(db, user_id)

    profile_values = {
        key: fields[key]
        for key in ("exam_date", "weekly_study_hours", "experience_level")
        if key in fields
    }

    try:
        if "display_name" in fields:
            await users_repo.update_display_name(db, user_id, fields["display_name"])
        if profile_values:
            # Users created outside provision_user (seed data, hand-written SQL)
            # may have no profile row; without it the UPDATE below would change
            # nothing and still return 200.
            await users_repo.ensure_learner_profile(db, user_id)
            await users_repo.update_learner_profile(db, user_id, profile_values)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await users_repo.get_user_by_id(db, user_id)
