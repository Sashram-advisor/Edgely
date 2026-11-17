"""GET /certifications - the catalog a learner can enroll in.

Needs a valid login, but not a platform user: a learner can browse the catalog
before POST /users/me has run. Register with app.include_router(router).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import get_db
from app.schemas.enrollment import CertificationOut
from app.services import enrollment_service

router = APIRouter(prefix="/certifications", tags=["certifications"])


@router.get(
    "",
    response_model=list[CertificationOut],
    responses={401: {"description": "Missing or invalid access token"}},
)
async def list_certifications(
    _auth: AuthenticatedUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Active certifications, ordered by name."""
    return await enrollment_service.list_certifications(db)
