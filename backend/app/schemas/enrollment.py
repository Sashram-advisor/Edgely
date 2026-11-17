"""Request and response models for the learning catalog: certifications and enrollments."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The four values allowed by enrollments_status_check in Database_inital.
EnrollmentStatus = Literal["active", "paused", "completed", "abandoned"]

# One week has 168 hours; matches enrollments_weekly_hours_check and the
# enrollments_check_total_hours trigger.
MAX_WEEKLY_HOURS = Decimal("168")

WeeklyHours = Field(default=None, gt=0, le=MAX_WEEKLY_HOURS, max_digits=5, decimal_places=2)


class CertificationOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None


class EnrollmentCreate(BaseModel):
    """Body of POST /enrollments. Only certification_id is required."""

    model_config = ConfigDict(extra="forbid")

    certification_id: int = Field(gt=0)
    goal: str | None = Field(default=None, max_length=2000)
    deadline: date | None = None
    weekly_study_hours: Decimal | None = WeeklyHours


class EnrollmentUpdate(BaseModel):
    """Body of PATCH /enrollments/{id}. Send only the fields to change.

    goal, deadline and weekly_study_hours may be sent as null to clear them.
    status can never be null.
    """

    model_config = ConfigDict(extra="forbid")

    status: EnrollmentStatus | None = None
    goal: str | None = Field(default=None, max_length=2000)
    deadline: date | None = None
    weekly_study_hours: Decimal | None = WeeklyHours


class EnrollmentOut(BaseModel):
    id: int
    certification_id: int
    certification_name: str
    certification_slug: str
    status: EnrollmentStatus
    goal: str | None = None
    deadline: date | None = None
    # float, not Decimal, so the JSON carries a number rather than a string.
    weekly_study_hours: float | None = None
    created_at: datetime
