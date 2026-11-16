"""Enrollment routes: list mine, enroll, and change an enrollment.

The learner always comes from the login token (current_user_id), never the body.
Register with app.include_router(router).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.schemas.enrollment import EnrollmentCreate, EnrollmentOut, EnrollmentUpdate
from app.services import enrollment_service

try:
    # Shared dependency from the identity workstream (core/dependencies.py).
    from app.core.dependencies import current_user_id
except ImportError:  # until it lands, use the same function where it lives today
    from app.routes.tutor import current_user_id

router = APIRouter(prefix="/enrollments", tags=["enrollments"])

_AUTH_ERRORS = {
    401: {"description": "Missing or invalid access token"},
    403: {"description": "Valid token, but no platform user yet: call POST /users/me first"},
}


@router.get("/me", response_model=list[EnrollmentOut], responses=_AUTH_ERRORS)
async def my_enrollments(
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """All of the learner's enrollments, newest first, including completed and abandoned ones."""
    return await enrollment_service.list_enrollments(db, user_id)


@router.post(
    "",
    response_model=EnrollmentOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        **_AUTH_ERRORS,
        409: {"description": "An active or paused enrollment for this certification already exists"},
        422: {"description": "Unknown or inactive certification, or weekly hours over 168"},
    },
)
async def enroll(
    body: EnrollmentCreate,
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enroll in a certification. The new enrollment starts as active."""
    return await enrollment_service.create_enrollment(db, user_id, body)


@router.patch(
    "/{enrollment_id}",
    response_model=EnrollmentOut,
    responses={
        **_AUTH_ERRORS,
        404: {"description": "No enrollment with this id belongs to you"},
        422: {"description": "Status change not allowed, enrollment closed, or weekly hours over 168"},
    },
)
async def update_enrollment(
    body: EnrollmentUpdate,
    enrollment_id: int = Path(gt=0),
    user_id: int = Depends(current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change status (active <-> paused, or close as completed / abandoned) or study details."""
    return await enrollment_service.update_enrollment(db, user_id, enrollment_id, body)
