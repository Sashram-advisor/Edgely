"""Shared request dependencies for the Edgely domain API.

Why this module exists
----------------------
``core.auth_provider`` proves *who* the caller is (it validates the Supabase
JWT and returns an ``AuthenticatedUser``). Edgely's own tables, however, are
keyed by ``users.id`` - a local BIGINT that has nothing to do with the
Supabase ``sub`` claim. Every domain route needs the translation, and a route
that forgets it either trusts a client-supplied id or crashes.

Keeping the translation in one place means:

* there is exactly one query that maps ``external_auth_id`` -> ``users.id``;
* the tutor routes and the new ``/users`` routes cannot drift apart;
* integration tests can override a single dependency.

Security rule: the platform user id is **never** read from the request body or
query string. It is derived from the verified token only.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import fetch_one, get_db

# Kept as a module constant so tests and reviewers can see the exact query.
# ``external_auth_id`` is UNIQUE in Database_inital, so this returns at most one row.
_SELECT_PLATFORM_USER_ID = "SELECT id FROM users WHERE external_auth_id = :auth_id"


async def current_user_id(
    auth: AuthenticatedUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Return the platform ``users.id`` for the verified Supabase login.

    Raises:
        HTTPException: 403 when the token is valid but no platform user exists
            yet. The client is expected to call ``POST /users/me`` once to
            provision the row (see ``services/user_service.provision_user``).

    The 403 (rather than 404) is deliberate: the login is authenticated, but
    it is not yet authorised to act as a platform user. That is also the shape
    the existing tutor routes already return, so clients only handle one case.
    """

    row = await fetch_one(
        db,
        _SELECT_PLATFORM_USER_ID,
        {"auth_id": auth.auth_id},
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No platform user exists for this login",
        )

    # asyncpg returns BIGINT as int already; the cast keeps the contract stable
    # if the column type ever changes to NUMERIC/DECIMAL.
    return int(row["id"])
