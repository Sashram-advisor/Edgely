"""scripts/link_user.py, with Supabase and the database replaced (no network, no Postgres)."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "link_user.py"


@pytest.fixture
def link_user(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "test-secret-key")
    spec = importlib.util.spec_from_file_location("link_user_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, users: list[dict]) -> None:
        self._users = users

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"users": self._users}


def _fake_supabase(monkeypatch, module, pages: list[list[dict]]) -> list[int]:
    requested: list[int] = []

    def fake_get(url, headers, params, timeout):
        assert url == "https://example.supabase.co/auth/v1/admin/users"
        assert headers["Authorization"] == "Bearer test-secret-key"
        requested.append(params["page"])
        return _Response(pages[params["page"] - 1] if params["page"] <= len(pages) else [])

    monkeypatch.setattr(module.httpx, "get", fake_get)
    return requested


def test_finds_email_case_insensitively(monkeypatch, link_user) -> None:
    _fake_supabase(monkeypatch, link_user, [[{"id": "a1", "email": "Other@x.com"}, {"id": "a2", "email": "Maya@Example.com"}]])
    assert link_user.supabase_user_id(" maya@example.com ") == "a2"


def test_searches_past_the_first_page(monkeypatch, link_user) -> None:
    monkeypatch.setattr(link_user, "PAGE_SIZE", 2)
    full_page = [{"id": "x", "email": "x@x.com"}, {"id": "y", "email": "y@x.com"}]
    requested = _fake_supabase(monkeypatch, link_user, [full_page, [{"id": "z", "email": "maya@example.com"}]])
    assert link_user.supabase_user_id("maya@example.com") == "z"
    assert requested == [1, 2]


def test_unknown_email_exits_with_a_message(monkeypatch, link_user) -> None:
    _fake_supabase(monkeypatch, link_user, [[{"id": "a1", "email": "other@x.com"}]])
    with pytest.raises(SystemExit, match="No Supabase login found"):
        link_user.supabase_user_id("maya@example.com")


def test_link_provisions_through_the_service_and_closes_the_pool(monkeypatch, link_user) -> None:
    _fake_supabase(monkeypatch, link_user, [[{"id": "auth-maya", "email": "maya@example.com"}]])
    seen: dict = {}

    class _Session:
        async def __aenter__(self):
            return "session"

        async def __aexit__(self, *exc):
            return False

    async def fake_provision(db, auth_id, email=None, display_name=None):
        seen.update(db=db, auth_id=auth_id, email=email)
        return {"id": 7, "external_auth_id": auth_id, "email": email}

    async def fake_close_db():
        seen["closed"] = True

    monkeypatch.setattr(link_user, "SessionLocal", _Session)
    monkeypatch.setattr(link_user, "provision_user", fake_provision)
    monkeypatch.setattr(link_user, "close_db", fake_close_db)

    row = asyncio.run(link_user.link("maya@example.com"))
    assert row["id"] == 7
    assert seen == {"db": "session", "auth_id": "auth-maya", "email": "maya@example.com", "closed": True}
