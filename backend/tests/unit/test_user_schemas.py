"""Unit tests for the user schemas and the provisioning fallbacks.

These tests do not touch a database and do not import FastAPI, so they run in a
minimal environment. Route-level behaviour lives in
``backend/tests/integration/test_users_api.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.user import UserUpdate
from app.services.user_service import _fallback_display_name, _fallback_email


def test_display_name_is_trimmed() -> None:
    update = UserUpdate(display_name="  Maya  ")
    assert update.display_name == "Maya"


def test_blank_display_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserUpdate(display_name="   ")


def test_null_display_name_is_rejected() -> None:
    # Omitted is fine, explicit null is not: users.display_name is NOT NULL.
    with pytest.raises(ValidationError):
        UserUpdate(display_name=None)


def test_weekly_study_hours_bounds() -> None:
    assert UserUpdate(weekly_study_hours=0).weekly_study_hours == 0
    assert UserUpdate(weekly_study_hours=168).weekly_study_hours == 168
    with pytest.raises(ValidationError):
        UserUpdate(weekly_study_hours=169)
    with pytest.raises(ValidationError):
        UserUpdate(weekly_study_hours=-1)


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UserUpdate(weekly_hours=10)  # type: ignore[call-arg]


def test_exclude_unset_keeps_only_sent_fields() -> None:
    assert UserUpdate(exam_date=None).model_dump(exclude_unset=True) == {"exam_date": None}
    assert UserUpdate(display_name="Maya").model_dump(exclude_unset=True) == {"display_name": "Maya"}


def test_provisioning_fallbacks_are_deterministic() -> None:
    assert _fallback_email("abc-123") == "abc-123@unknown.invalid"
    assert _fallback_display_name("maya.chen@example.com") == "maya.chen"
    assert _fallback_display_name("@example.com") == "Learner"
