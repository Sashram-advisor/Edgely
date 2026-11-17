"""The learner's own account endpoints.

Route shape follows the M1 contract (``docs/api/m1-contract.md``):

* ``POST /users/me``  - provision on first login, idempotent, 200.
* ``GET /users/me``   - read my profile (403 until provisioned).
* ``PATCH /users/me`` - update my name and study preferences.

All three derive the user id from the verified token. ``POST`` uses the raw
auth identity because no platform row exists on the first call; ``GET`` and
``PATCH`` use ``core.dependencies.current_user_id``. No route accepts a user id
from the caller.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import get_db
from app.core.dependencies import current_user_id
from app.schemas.user import UserRead, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Create my platform user (idempotent)",
)
async def provision_me(
    auth: AuthenticatedUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Provision the platform user for the current login and return it.

    This is the only route that does not go through ``current_user_id``,
    because on the very first call that dependency would raise 403 by design.
    Calling it again is safe: the upsert keys on ``external_auth_id`` and the
    learner profile insert is ``ON CONFLICT DO NOTHING``.
    """

    row = await user_service.provision_user(db, auth.auth_id, email=auth.email)
    return UserRead.model_validate(row)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Read my profile",
)
async def read_me(
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Return the joined user/profile row for the logged-in learner.

    ``current_user_id`` already guarantees the row exists; the extra check only
    protects against a concurrent delete between the two queries.
    """

    row = await user_service.get_user(db, user_id)
    if row is None:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform user not found",
        )
    return UserRead.model_validate(row)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update my profile",
)
async def update_me(
    update: UserUpdate,
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Apply a partial update to the caller's own record.

    Only ``display_name`` lives on ``users``; the study fields live on
    ``learner_profiles``. The service writes both in one transaction, so a
    request that changes a name and an exam date either applies fully or not
    at all.
    """

    row = await user_service.update_user(db, user_id, update)
    if row is None:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform user not found",
        )
    return UserRead.model_validate(row)
