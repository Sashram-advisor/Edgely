"""Team A P1 checks on the real /tutor routes (T3, T4). Offline: no Supabase, no Claude.

The tutor's prepare/stream functions are monkeypatched, so these tests exercise
the HTTP layer (auth dependency, rate limit, SSE framing, error sanitising) and
the pure helpers in chat.py, not the model.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core import dependencies as auth_dependencies
from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import get_db
from app.core.rate_limit import InMemoryRateLimiter, Window
from app.core import rate_limit
from app.merged_main import app
from app.routes import tutor as tutor_routes

SECRET = "relation \"messages\" violates constraint; key=sk-ant-api03-SECRET"


@pytest.fixture
def client(monkeypatch) -> TestClient:
    """A client logged in as auth id 'auth-abc' -> platform user 7, with a fresh 2/minute limiter."""

    async def fake_db():
        yield object()

    async def fake_fetch_one(db, sql, params=None):
        return {"id": 7}

    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(auth_id="auth-abc", email=None)
    app.dependency_overrides[get_db] = fake_db
    monkeypatch.setattr(auth_dependencies, "fetch_one", fake_fetch_one)
    # A small, isolated limiter so the test does not depend on .env values.
    monkeypatch.setattr(rate_limit, "tutor_limiter", InMemoryRateLimiter([Window(2, 60)]))
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


def _events(body: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into [(event, data), ...]."""
    out = []
    for frame in body.split("\n\n"):
        if not frame.strip():
            continue
        lines = dict(line.split(": ", 1) for line in frame.split("\n"))
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def _fake_prep():
    return SimpleNamespace(conversation_id=42, standalone_query="What is S3?")


# --- T4: rate limit -------------------------------------------------------------------------


def test_third_question_in_a_minute_is_429_with_retry_after(client, monkeypatch) -> None:
    chat_module = tutor_routes._tutor()[0]
    monkeypatch.setattr(chat_module, "chat_turn", lambda req: {"answer": "ok"})

    assert client.post("/tutor/chat", json={"message": "q1"}).status_code == 200
    assert client.post("/tutor/chat", json={"message": "q2"}).status_code == 200
    response = client.post("/tutor/chat", json={"message": "q3"})

    assert response.status_code == 429
    assert 1 <= int(response.headers["Retry-After"]) <= 60
    assert response.headers["X-Error-Code"] == "TUTOR_RATE_LIMITED"
    assert isinstance(response.json()["detail"], str)


def test_stream_and_plain_chat_share_one_limit(client, monkeypatch) -> None:
    chat_module = tutor_routes._tutor()[0]
    monkeypatch.setattr(chat_module, "chat_turn", lambda req: {"answer": "ok"})
    monkeypatch.setattr(chat_module, "prepare_turn", lambda req: _fake_prep())
    monkeypatch.setattr(chat_module, "stream_turn", lambda prep: iter([("done", {"answer": "ok"})]))

    assert client.post("/tutor/chat", json={"message": "q1"}).status_code == 200
    assert client.post("/tutor/chat/stream", json={"message": "q2"}).status_code == 200
    assert client.post("/tutor/chat/stream", json={"message": "q3"}).status_code == 429


def test_rate_limit_runs_before_any_model_work(client, monkeypatch) -> None:
    chat_module = tutor_routes._tutor()[0]
    calls = []
    monkeypatch.setattr(chat_module, "chat_turn", lambda req: calls.append(req) or {"answer": "ok"})
    for _ in range(5):
        client.post("/tutor/chat", json={"message": "q"})
    assert len(calls) == 2  # questions 3-5 never reached the tutor


def test_unauthenticated_requests_are_401_not_429() -> None:
    # The limiter keys on the verified user, so without a token auth fails first.
    response = TestClient(app, raise_server_exceptions=False).post("/tutor/chat", json={"message": "hi"})
    assert response.status_code == 401


# --- T3: SSE contract and sanitised errors -----------------------------------------------------


def test_stream_happy_path_follows_the_contract(client, monkeypatch) -> None:
    chat_module = tutor_routes._tutor()[0]
    monkeypatch.setattr(chat_module, "prepare_turn", lambda req: _fake_prep())
    monkeypatch.setattr(
        chat_module,
        "stream_turn",
        lambda prep: iter([("delta", "S3 is "), ("delta", "object storage [S1]."), ("done", {"answer": "x"})]),
    )

    response = client.post("/tutor/chat/stream", json={"message": "What is S3?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    names = [name for name, _ in _events(response.text)]
    assert names == ["meta", "delta", "delta", "done"]
    assert _events(response.text)[0][1] == {"conversation_id": 42, "standalone_query": "What is S3?"}


def test_stream_error_is_sanitised(client, monkeypatch) -> None:
    chat_module = tutor_routes._tutor()[0]

    def failing_stream(prep):
        yield "delta", "partial "
        raise RuntimeError(SECRET)

    monkeypatch.setattr(chat_module, "prepare_turn", lambda req: _fake_prep())
    monkeypatch.setattr(chat_module, "stream_turn", failing_stream)

    response = client.post("/tutor/chat/stream", json={"message": "What is S3?"})

    assert "SECRET" not in response.text and "violates constraint" not in response.text
    events = _events(response.text)
    assert [name for name, _ in events] == ["meta", "delta", "error"]
    error = events[-1][1]
    assert error["code"] == "TUTOR_INTERNAL_ERROR"
    assert set(error) == {"code", "message", "retryable", "error_id", "detail"}


# --- T4: fewer model calls, recorded tokens ---------------------------------------------------


def test_needs_rewrite_heuristic() -> None:
    chat_module = tutor_routes._tutor()[0]
    history = [{"role": "user", "content": "What is S3?"}, {"role": "assistant", "content": "Object storage."}]

    # First message of a thread: never (nothing to resolve).
    assert chat_module.needs_rewrite([], "what about it?", "always") is False
    # Clear standalone question: skip the extra call.
    assert chat_module.needs_rewrite(history, "Explain the storage classes available in Amazon S3 Glacier") is False
    # Follow-ups: rewrite.
    assert chat_module.needs_rewrite(history, "What about Glacier?") is True
    assert chat_module.needs_rewrite(history, "How much does it cost per gigabyte stored?") is True
    assert chat_module.needs_rewrite(history, "why?") is True
    # Modes.
    assert chat_module.needs_rewrite(history, "Explain the storage classes available in Amazon S3 Glacier", "always") is True
    assert chat_module.needs_rewrite(history, "What about Glacier?", "off") is False


def test_turn_usage_includes_the_rewrite_call() -> None:
    chat_module = tutor_routes._tutor()[0]
    prep = SimpleNamespace(rewrite_usage=chat_module.RewriteUsage(input_tokens=50, output_tokens=12, called=True))
    answer_usage = SimpleNamespace(
        input_tokens=1000, output_tokens=200, cache_read_input_tokens=300, cache_creation_input_tokens=None
    )

    usage = chat_module._turn_usage(prep, answer_usage)

    assert usage["input_tokens"] == 1000  # pre-P1 keys unchanged
    assert usage["rewrite_input_tokens"] == 50
    assert usage["total_input_tokens"] == 1000 + 300 + 50
    assert usage["total_output_tokens"] == 200 + 12
