"""Route-level tests for ``/users/me``.

The tests never touch Postgres: ``get_db`` is overridden with an inert session
and the service functions are monkeypatched. That keeps the contract tests fast
and makes the assertion about *which* user id is used explicit.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import dependencies as auth_dependencies
from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import get_db
from app.core.dependencies import current_user_id
from app.main import app
from app.services import user_service

_USER_ROW = {
    "id": 7,
    "external_auth_id": "auth-abc",
    "display_name": "Maya",
    "email": "maya@example.com",
    "role": "learner",
    "created_at": None,
    "target_certification_id": None,
    "exam_date": None,
    "weekly_study_hours": None,
    "experience_level": None,
}


class _FakeSession:
    """Enough of an AsyncSession for dependency injection; never used for I/O."""


async def _fake_db():
    yield _FakeSession()


def _client() -> TestClient:
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[current_user_id] = lambda: 7
    return TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_provision_uses_the_token_identity(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    async def fake_provision(db, auth_id, email=None, display_name=None):
        seen["auth_id"] = auth_id
        seen["email"] = email
        return _USER_ROW

    monkeypatch.setattr(user_service, "provision_user", fake_provision)
    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(
        auth_id="auth-abc",
        email="maya@example.com",
    )

    response = _client().post("/users/me", json={"user_id": 999})

    assert response.status_code == 200
    assert response.json()["id"] == 7
    assert seen == {"auth_id": "auth-abc", "email": "maya@example.com"}


def test_get_me_returns_the_token_user(monkeypatch) -> None:
    async def fake_get_user(db, user_id):
        assert user_id == 7
        return _USER_ROW

    monkeypatch.setattr(user_service, "get_user", fake_get_user)
    response = _client().get("/users/me")
    assert response.status_code == 200
    assert response.json()["external_auth_id"] == "auth-abc"


def test_get_me_without_platform_user_is_403(monkeypatch) -> None:
    async def fake_fetch_one(db, sql, params=None):
        return None

    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(
        auth_id="nobody",
        email=None,
    )
    monkeypatch.setattr(auth_dependencies, "fetch_one", fake_fetch_one)

    response = TestClient(app, raise_server_exceptions=False).get("/users/me")
    assert response.status_code == 403


def test_patch_sends_only_the_fields_the_client_sent(monkeypatch) -> None:
    seen: dict[str, object] = {}

    async def fake_update(db, user_id, update):
        seen["values"] = update.model_dump(exclude_unset=True)
        return _USER_ROW

    monkeypatch.setattr(user_service, "update_user", fake_update)
    response = _client().patch("/users/me", json={"exam_date": None})

    assert response.status_code == 200
    assert seen["values"] == {"exam_date": None}


def test_patch_rejects_null_display_name() -> None:
    response = _client().patch("/users/me", json={"display_name": None})
    assert response.status_code == 422


def test_patch_rejects_out_of_range_study_hours() -> None:
    response = _client().patch("/users/me", json={"weekly_study_hours": 200})
    assert response.status_code == 422


def test_provision_passes_display_name_from_body(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    async def fake_provision(db, auth_id, email=None, display_name=None):
        seen["display_name"] = display_name
        return _USER_ROW

    monkeypatch.setattr(user_service, "provision_user", fake_provision)
    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(auth_id="auth-abc", email=None)

    assert _client().post("/users/me", json={"display_name": "Maya Chen"}).status_code == 200
    assert seen["display_name"] == "Maya Chen"

    assert _client().post("/users/me").status_code == 200  # the body stays optional
    assert seen["display_name"] is None
