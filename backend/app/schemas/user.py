"""Pydantic models for the ``/users`` API.

These models are the public contract. They are intentionally flat: the API
joins ``users`` and ``learner_profiles`` so a client gets one object instead of
two, and the field names match the database columns one-to-one.

Validation choices worth knowing:

* ``display_name`` is trimmed and cannot be blank after trimming.
* ``weekly_study_hours`` is capped at 168 (hours in a week). The enrolment
  trigger enforces the same limit, but rejecting it here produces a clean 422
  instead of a database error.
* ``UserUpdate`` forbids unknown fields so a typo like ``weekly_hours`` fails
  loudly rather than being silently ignored.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ExperienceLevel = Literal["beginner", "intermediate", "advanced"]


class UserRead(BaseModel):
    """One platform user, joined with the learner profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_auth_id: str
    display_name: str
    email: str
    role: str
    created_at: datetime | None = None

    # learner_profiles columns. They are nullable in the database, and a row can
    # exist with every optional field empty right after provisioning.
    target_certification_id: int | None = None
    exam_date: date | None = None
    weekly_study_hours: int | None = None
    experience_level: str | None = None


class UserProvision(BaseModel):
    """Optional body of ``POST /users/me``.

    ``display_name`` is used only when the user is created; a later call never
    renames an existing user (use ``PATCH /users/me`` for that). Unknown fields
    are ignored, so a stray ``user_id`` has no effect.
    """

    model_config = ConfigDict(extra="ignore")

    display_name: str | None = Field(default=None, max_length=255)


class UserUpdate(BaseModel):
    """Fields a learner may change about themselves.

    Every field is optional. ``PATCH /users/me`` uses
    ``model_dump(exclude_unset=True)``, so an omitted field keeps its current
    value while an explicit ``null`` clears a nullable profile column.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    exam_date: date | None = None
    weekly_study_hours: int | None = Field(default=None, ge=0, le=168)
    experience_level: ExperienceLevel | None = None

    @field_validator("display_name")
    @classmethod
    def strip_and_reject_blank(cls, value: str | None) -> str | None:
        """Trim surrounding spaces and reject a value that is only whitespace."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("display_name cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def reject_null_display_name(self) -> "UserUpdate":
        """Refuse ``{"display_name": null}``.

        Omitted is fine (the field keeps its value); null is not, because
        ``users.display_name`` is NOT NULL. Pydantic otherwise cannot tell the
        two cases apart once ``exclude_unset`` is applied later.
        """
        if "display_name" in self.model_fields_set and self.display_name is None:
            raise ValueError("display_name cannot be null")
        return self
