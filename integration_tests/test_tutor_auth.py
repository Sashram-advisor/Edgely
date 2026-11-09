"""The tutor routes must take the learner from the login token, never from the request body."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import get_db
from app.merged_main import app
from app.routes import tutor as tutor_routes


class _FakeSession:
    pass


def _client_logged_in_as(auth_id: str) -> TestClient:
    async def fake_db():
        yield _FakeSession()

    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(auth_id=auth_id, email=None)
    app.dependency_overrides[get_db] = fake_db
    return TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_tutor_routes_registered() -> None:
    # FastAPI 0.162 includes routers lazily, so read the effective paths from OpenAPI.
    paths = set(app.openapi()["paths"])
    assert "/tutor/chat" in paths
    assert "/tutor/chat/stream" in paths
    assert "/health/tutor" in paths


def test_chat_without_token_is_401() -> None:
    response = TestClient(app, raise_server_exceptions=False).post("/tutor/chat", json={"message": "hi"})
    assert response.status_code == 401


def test_user_id_comes_from_the_token_not_the_body(monkeypatch) -> None:
    async def fake_fetch_one(db, sql, params=None):
        assert params == {"auth_id": "auth-abc"}
        return {"id": 7}

    seen = {}

    def fake_chat_turn(req):
        seen["user_id"] = req.user_id
        return {"answer": "ok"}

    monkeypatch.setattr(tutor_routes, "fetch_one", fake_fetch_one)
    chat_module, _, _ = tutor_routes._tutor()
    monkeypatch.setattr(chat_module, "chat_turn", fake_chat_turn)

    client = _client_logged_in_as("auth-abc")
    response = client.post("/tutor/chat", json={"message": "hi", "user_id": 999})

    assert response.status_code == 200
    assert seen["user_id"] == 7


def test_login_without_a_platform_user_is_403(monkeypatch) -> None:
    async def fake_fetch_one(db, sql, params=None):
        return None

    monkeypatch.setattr(tutor_routes, "fetch_one", fake_fetch_one)
    response = _client_logged_in_as("nobody").post("/tutor/chat", json={"message": "hi"})
    assert response.status_code == 403


def test_not_enrolled_becomes_403(monkeypatch) -> None:
    async def fake_fetch_one(db, sql, params=None):
        return {"id": 7}

    def raise_not_enrolled(req):
        raise tutor_routes._tutor()[0].NotEnrolled("not enrolled")

    monkeypatch.setattr(tutor_routes, "fetch_one", fake_fetch_one)
    monkeypatch.setattr(tutor_routes._tutor()[0], "chat_turn", raise_not_enrolled)
    response = _client_logged_in_as("auth-abc").post("/tutor/chat", json={"message": "hi"})
    assert response.status_code == 403