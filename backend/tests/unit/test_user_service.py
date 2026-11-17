"""user_service rules, with the repository replaced by recorders (no database)."""

from __future__ import annotations

import asyncio

from app.repositories import users as users_repo
from app.schemas.user import UserUpdate
from app.services import user_service


class _Session:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


def _record(monkeypatch) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    async def upsert_user(db, **kwargs):
        calls.append(("upsert_user", kwargs))
        return 7

    async def ensure_learner_profile(db, user_id):
        calls.append(("ensure_learner_profile", {"user_id": user_id}))

    async def update_learner_profile(db, user_id, values):
        calls.append(("update_learner_profile", values))
        return 1

    async def update_display_name(db, user_id, display_name):
        calls.append(("update_display_name", {"display_name": display_name}))
        return 1

    async def get_user_by_id(db, user_id):
        return {"id": user_id}

    for name, fn in locals().items():
        if callable(fn) and hasattr(users_repo, name):
            monkeypatch.setattr(users_repo, name, fn)
    return calls


def test_token_without_email_does_not_overwrite_the_stored_email(monkeypatch) -> None:
    calls = _record(monkeypatch)
    asyncio.run(user_service.provision_user(_Session(), "auth-abc", email=None))
    upsert = dict(calls)["upsert_user"]
    assert upsert["email"] == "auth-abc@unknown.invalid"  # used only if the user is new
    assert upsert["refresh_email"] is False


def test_token_with_email_refreshes_it(monkeypatch) -> None:
    calls = _record(monkeypatch)
    asyncio.run(user_service.provision_user(_Session(), "auth-abc", email="  maya@example.com "))
    upsert = dict(calls)["upsert_user"]
    assert upsert["email"] == "maya@example.com"
    assert upsert["refresh_email"] is True


def test_profile_patch_creates_a_missing_profile_row_first(monkeypatch) -> None:
    calls = _record(monkeypatch)
    asyncio.run(user_service.update_user(_Session(), 7, UserUpdate(weekly_study_hours=5)))
    names = [name for name, _ in calls]
    assert names.index("ensure_learner_profile") < names.index("update_learner_profile")


def test_name_only_patch_does_not_touch_the_profile(monkeypatch) -> None:
    calls = _record(monkeypatch)
    asyncio.run(user_service.update_user(_Session(), 7, UserUpdate(display_name="Maya")))
    assert [name for name, _ in calls] == ["update_display_name"]
