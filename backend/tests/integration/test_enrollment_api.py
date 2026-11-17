"""Certification catalog and enrollment API (P0-2).

Two layers:

* API tests run everywhere. They drive the real routes and service through
  FastAPI's TestClient, with the repository swapped for an in-memory copy that
  follows the same rules as the database (one open enrollment per
  certification, 168-hour weekly cap).

* Database tests run only when EDGELY_TEST_DATABASE_URL points at an empty,
  disposable Postgres database. They apply Database_inital into a throwaway
  schema and check the real SQL: ON CONFLICT on the partial unique index, the
  weekly-hours trigger, and the error mapping.

      EDGELY_TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/edgely_test

When the shared fixture in backend/tests/conftest.py lands, the environment
setup and the database bootstrap below can move there.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]

# Dummy settings so app.core.config / app.core.db import without a real .env.
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/postgres")
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.repositories import enrollments as repo  # noqa: E402
from app.routes import certifications as certifications_routes  # noqa: E402
from app.routes import enrollments as enrollments_routes  # noqa: E402
from app.schemas.enrollment import EnrollmentCreate, EnrollmentUpdate  # noqa: E402
from app.services import enrollment_service  # noqa: E402

USER = 7
OTHER_USER = 8


# --------------------------------------------------------------------------
# In-memory repository with the database's rules
# --------------------------------------------------------------------------


class FakeStore:
    def __init__(self) -> None:
        self.certifications = {
            1: {"id": 1, "name": "AWS Cloud Practitioner", "slug": "aws-ccp", "description": "Intro", "is_active": True},
            2: {"id": 2, "name": "Azure Fundamentals", "slug": "az-900", "description": None, "is_active": True},
            3: {"id": 3, "name": "Retired Cert", "slug": "retired", "description": None, "is_active": False},
        }
        self.enrollments: dict[int, dict] = {}
        self.next_id = 1

    def _view(self, row: dict) -> dict:
        cert = self.certifications[row["certification_id"]]
        return {
            **{k: row[k] for k in ("id", "certification_id", "status", "goal", "deadline", "weekly_study_hours", "created_at")},
            "certification_name": cert["name"],
            "certification_slug": cert["slug"],
        }

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store = self

        async def list_active_certifications(db):
            return [
                {k: c[k] for k in ("id", "name", "slug", "description")}
                for c in sorted(store.certifications.values(), key=lambda c: c["name"])
                if c["is_active"]
            ]

        async def get_active_certification(db, certification_id):
            c = store.certifications.get(certification_id)
            return {k: c[k] for k in ("id", "name", "slug", "description")} if c and c["is_active"] else None

        async def list_for_user(db, user_id):
            rows = [r for r in store.enrollments.values() if r["user_id"] == user_id]
            return [store._view(r) for r in sorted(rows, key=lambda r: r["id"], reverse=True)]

        async def get_for_user(db, enrollment_id, user_id):
            r = store.enrollments.get(enrollment_id)
            return store._view(r) if r and r["user_id"] == user_id else None

        async def open_hours_for_user(db, user_id, exclude_enrollment_id=None):
            return sum(
                (Decimal(r["weekly_study_hours"] or 0) for r in store.enrollments.values()
                 if r["user_id"] == user_id and r["status"] in ("active", "paused") and r["id"] != exclude_enrollment_id),
                Decimal(0),
            )

        async def insert_open_enrollment(db, *, user_id, certification_id, goal, deadline, weekly_study_hours):
            if any(r["user_id"] == user_id and r["certification_id"] == certification_id
                   and r["status"] in ("active", "paused") for r in store.enrollments.values()):
                return None  # ON CONFLICT DO NOTHING
            new_id = store.next_id
            store.next_id += 1
            store.enrollments[new_id] = {
                "id": new_id, "user_id": user_id, "certification_id": certification_id, "status": "active",
                "goal": goal, "deadline": deadline, "weekly_study_hours": weekly_study_hours,
                "created_at": datetime(2026, 11, 16, tzinfo=timezone.utc),
            }
            return new_id

        async def update_enrollment(db, enrollment_id, user_id, changes):
            r = store.enrollments.get(enrollment_id)
            if not r or r["user_id"] != user_id:
                return False
            r.update(changes)
            return True

        for name, fn in list(locals().items()):
            if callable(fn) and name != "store" and hasattr(repo, name):
                monkeypatch.setattr(repo, name, fn)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.fixture
def store(monkeypatch: pytest.MonkeyPatch) -> FakeStore:
    s = FakeStore()
    s.install(monkeypatch)
    return s


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(certifications_routes.router)
    app.include_router(enrollments_routes.router)
    return app


@pytest.fixture
def client(store: FakeStore):
    app = _app()
    state = {"user_id": USER}

    async def fake_db():
        yield FakeSession()

    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(auth_id="auth-abc", email=None)
    app.dependency_overrides[enrollments_routes.current_user_id] = lambda: state["user_id"]
    app.dependency_overrides[get_db] = fake_db
    c = TestClient(app, raise_server_exceptions=False)
    c.state = state  # tests switch users with client.state["user_id"] = ...
    return c


def _enroll(client: TestClient, certification_id: int = 1, **extra) -> dict:
    response = client.post("/enrollments", json={"certification_id": certification_id, **extra})
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------
# Routes are registered and documented
# --------------------------------------------------------------------------


def test_routes_appear_in_openapi() -> None:
    paths = _app().openapi()["paths"]
    assert "get" in paths["/certifications"]
    assert "get" in paths["/enrollments/me"]
    assert "post" in paths["/enrollments"]
    assert "patch" in paths["/enrollments/{enrollment_id}"]
    assert "409" in paths["/enrollments"]["post"]["responses"]


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/certifications"), ("get", "/enrollments/me"), ("post", "/enrollments"), ("patch", "/enrollments/1")],
)
def test_no_token_is_401(method: str, path: str) -> None:
    response = TestClient(_app(), raise_server_exceptions=False).request(method.upper(), path, json={})
    assert response.status_code == 401


def test_valid_login_without_platform_user_is_403(store: FakeStore, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real current_user_id: valid token, no users row -> 403, before any enrollment work."""
    app = _app()

    async def fake_db():
        yield FakeSession()

    async def no_user(db, sql, params=None):
        return None

    monkeypatch.setattr(sys.modules[enrollments_routes.current_user_id.__module__], "fetch_one", no_user)
    app.dependency_overrides[get_current_auth_user] = lambda: AuthenticatedUser(auth_id="nobody", email=None)
    app.dependency_overrides[get_db] = fake_db
    client = TestClient(app, raise_server_exceptions=False)

    assert client.get("/enrollments/me").status_code == 403
    assert client.post("/enrollments", json={"certification_id": 1}).status_code == 403
    assert store.enrollments == {}


# --------------------------------------------------------------------------
# GET /certifications
# --------------------------------------------------------------------------


def test_lists_only_active_certifications(client: TestClient) -> None:
    response = client.get("/certifications")
    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "AWS Cloud Practitioner", "slug": "aws-ccp", "description": "Intro"},
        {"id": 2, "name": "Azure Fundamentals", "slug": "az-900", "description": None},
    ]


# --------------------------------------------------------------------------
# POST /enrollments and GET /enrollments/me
# --------------------------------------------------------------------------


def test_enroll_then_list(client: TestClient) -> None:
    assert client.get("/enrollments/me").json() == []

    created = _enroll(client, 1, goal="Pass in March", deadline="2027-03-01", weekly_study_hours=6.5)
    assert created["status"] == "active"
    assert created["certification_slug"] == "aws-ccp"
    assert created["weekly_study_hours"] == 6.5
    assert created["deadline"] == "2027-03-01"

    mine = client.get("/enrollments/me").json()
    assert [e["id"] for e in mine] == [created["id"]]


def test_duplicate_open_enrollment_is_409(client: TestClient, store: FakeStore) -> None:
    _enroll(client, 1)
    response = client.post("/enrollments", json={"certification_id": 1})
    assert response.status_code == 409
    assert len(store.enrollments) == 1


def test_paused_enrollment_still_blocks_a_duplicate(client: TestClient) -> None:
    first = _enroll(client, 1)
    client.patch(f"/enrollments/{first['id']}", json={"status": "paused"})
    assert client.post("/enrollments", json={"certification_id": 1}).status_code == 409


def test_can_reenroll_after_completing(client: TestClient) -> None:
    first = _enroll(client, 1)
    assert client.patch(f"/enrollments/{first['id']}", json={"status": "completed"}).status_code == 200
    second = _enroll(client, 1)
    assert second["id"] != first["id"]
    statuses = {e["id"]: e["status"] for e in client.get("/enrollments/me").json()}
    assert statuses == {first["id"]: "completed", second["id"]: "active"}


def test_two_users_can_enroll_in_the_same_certification(client: TestClient) -> None:
    _enroll(client, 1)
    client.state["user_id"] = OTHER_USER
    _enroll(client, 1)
    assert len(client.get("/enrollments/me").json()) == 1


@pytest.mark.parametrize("certification_id", [3, 999])
def test_inactive_or_unknown_certification_is_422(client: TestClient, certification_id: int) -> None:
    assert client.post("/enrollments", json={"certification_id": certification_id}).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"certification_id": "abc"},
        {"certification_id": 0},
        {"certification_id": 1, "weekly_study_hours": 0},
        {"certification_id": 1, "weekly_study_hours": 169},
        {"certification_id": 1, "user_id": 99},  # the learner never comes from the body
    ],
)
def test_invalid_body_is_422(client: TestClient, body: dict) -> None:
    assert client.post("/enrollments", json=body).status_code == 422


def test_weekly_hours_across_open_enrollments_capped_at_168(client: TestClient) -> None:
    _enroll(client, 1, weekly_study_hours=100)
    response = client.post("/enrollments", json={"certification_id": 2, "weekly_study_hours": 70})
    assert response.status_code == 422
    assert "168" in response.json()["detail"]
    _enroll(client, 2, weekly_study_hours=68)  # exactly 168 is allowed


# --------------------------------------------------------------------------
# PATCH /enrollments/{id}: the state machine
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "new", "allowed"),
    [
        ("active", "paused", True),
        ("active", "completed", True),
        ("active", "abandoned", True),
        ("active", "active", True),
        ("paused", "active", True),
        ("paused", "completed", True),
        ("paused", "abandoned", True),
        ("completed", "active", False),
        ("completed", "paused", False),
        ("abandoned", "active", False),
        ("abandoned", "completed", False),
    ],
)
def test_state_machine(current: str, new: str, allowed: bool) -> None:
    assert enrollment_service.can_transition(current, new) is allowed


def test_pause_and_resume(client: TestClient) -> None:
    e = _enroll(client, 1)
    assert client.patch(f"/enrollments/{e['id']}", json={"status": "paused"}).json()["status"] == "paused"
    assert client.patch(f"/enrollments/{e['id']}", json={"status": "active"}).json()["status"] == "active"


def test_closed_enrollment_cannot_change(client: TestClient) -> None:
    e = _enroll(client, 1)
    client.patch(f"/enrollments/{e['id']}", json={"status": "abandoned"})
    assert client.patch(f"/enrollments/{e['id']}", json={"status": "active"}).status_code == 422
    assert client.patch(f"/enrollments/{e['id']}", json={"goal": "new"}).status_code == 422


def test_update_details_and_clear_with_null(client: TestClient) -> None:
    e = _enroll(client, 1, goal="old", weekly_study_hours=5)
    updated = client.patch(f"/enrollments/{e['id']}", json={"goal": "new", "weekly_study_hours": None}).json()
    assert updated["goal"] == "new"
    assert updated["weekly_study_hours"] is None
    assert updated["status"] == "active"


def test_patch_weekly_hours_respects_cap(client: TestClient) -> None:
    _enroll(client, 1, weekly_study_hours=100)
    e2 = _enroll(client, 2, weekly_study_hours=10)
    assert client.patch(f"/enrollments/{e2['id']}", json={"weekly_study_hours": 80}).status_code == 422
    assert client.patch(f"/enrollments/{e2['id']}", json={"weekly_study_hours": 68}).status_code == 200


@pytest.mark.parametrize("body", [{"status": "deleted"}, {"status": None}, {"owner": 1}])
def test_patch_invalid_body_is_422(client: TestClient, body: dict) -> None:
    e = _enroll(client, 1)
    assert client.patch(f"/enrollments/{e['id']}", json=body).status_code == 422


def test_patch_missing_or_someone_elses_enrollment_is_404(client: TestClient) -> None:
    e = _enroll(client, 1)
    assert client.patch("/enrollments/999", json={"status": "paused"}).status_code == 404
    client.state["user_id"] = OTHER_USER
    assert client.patch(f"/enrollments/{e['id']}", json={"status": "abandoned"}).status_code == 404


# --------------------------------------------------------------------------
# Database errors that slip past the service checks still map to clean 4xx
# --------------------------------------------------------------------------


class _PgError(Exception):
    def __init__(self, sqlstate: str, message: str) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


@pytest.mark.parametrize(
    ("sqlstate", "message", "expected"),
    [
        ("23505", 'duplicate key value violates unique constraint "enrollments_one_open_per_cert"', 409),
        ("P0001", "Total weekly_study_hours of open enrollments (170) would exceed 168 for user 7", 422),
        ("23514", 'violates check constraint "enrollments_status_check"', 422),
        ("23503", "violates foreign key constraint", 422),
    ],
)
def test_database_errors_map_to_contract_codes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, sqlstate: str, message: str, expected: int
) -> None:
    from sqlalchemy.exc import DBAPIError

    async def racing_insert(db, **kwargs):
        raise DBAPIError("INSERT ...", {}, _PgError(sqlstate, message))

    monkeypatch.setattr(repo, "insert_open_enrollment", racing_insert)
    assert client.post("/enrollments", json={"certification_id": 1}).status_code == expected


def test_unknown_database_error_is_not_hidden(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.exc import DBAPIError

    async def broken_insert(db, **kwargs):
        raise DBAPIError("INSERT ...", {}, _PgError("08006", "connection failure"))

    monkeypatch.setattr(repo, "insert_open_enrollment", broken_insert)
    assert client.post("/enrollments", json={"certification_id": 1}).status_code == 500


# --------------------------------------------------------------------------
# Real Postgres: the SQL itself
# --------------------------------------------------------------------------

TEST_DB_URL = os.environ.get("EDGELY_TEST_DATABASE_URL")
SCHEMA_FILE = BACKEND / "app" / "database" / "migrations" / "Database_inital"

needs_db = pytest.mark.skipif(not TEST_DB_URL, reason="set EDGELY_TEST_DATABASE_URL to run database tests")


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def pg_session():
    """A session on a fresh schema built from Database_inital, dropped afterwards."""
    import asyncpg
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    raw_url = TEST_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
    schema = f"test_{uuid.uuid4().hex[:12]}"

    async def setup():
        conn = await asyncpg.connect(raw_url)
        try:
            await conn.execute(f'CREATE SCHEMA "{schema}"')
            await conn.execute(f'SET search_path TO "{schema}"')
            await conn.execute(SCHEMA_FILE.read_text(encoding="utf-8"))
            await conn.execute(
                """
                INSERT INTO users (id, external_auth_id, display_name, email, role) VALUES
                    (7, 'auth-7', 'Learner Seven', 'seven@example.com', 'learner'),
                    (8, 'auth-8', 'Learner Eight', 'eight@example.com', 'learner');
                INSERT INTO certifications (id, name, slug, description, is_active) VALUES
                    (1, 'AWS Cloud Practitioner', 'aws-ccp', 'Intro', true),
                    (2, 'Azure Fundamentals', 'az-900', NULL, true),
                    (3, 'Retired Cert', 'retired', NULL, false);
                """
            )
        finally:
            await conn.close()

    async def teardown():
        conn = await asyncpg.connect(raw_url)
        try:
            await conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await conn.close()

    _run(setup())
    url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})

    class Runner:
        def __call__(self, fn):
            async def go():
                async with AsyncSession(engine, expire_on_commit=False) as session:
                    return await fn(session)

            return _run(go())

    try:
        yield Runner()
    finally:
        _run(engine.dispose())
        _run(teardown())


@needs_db
def test_db_catalog_lists_only_active(pg_session) -> None:
    certs = pg_session(enrollment_service.list_certifications)
    assert [c["slug"] for c in certs] == ["aws-ccp", "az-900"]


@needs_db
def test_db_enroll_duplicate_and_reenroll(pg_session) -> None:
    from fastapi import HTTPException

    created = pg_session(lambda db: enrollment_service.create_enrollment(
        db, 7, EnrollmentCreate(certification_id=1, weekly_study_hours=Decimal("6.5"), deadline=date(2027, 3, 1))))
    assert created["status"] == "active"
    assert created["weekly_study_hours"] == Decimal("6.50")

    with pytest.raises(HTTPException) as dup:
        pg_session(lambda db: enrollment_service.create_enrollment(db, 7, EnrollmentCreate(certification_id=1)))
    assert dup.value.status_code == 409

    # A different learner is unaffected by the partial unique index.
    pg_session(lambda db: enrollment_service.create_enrollment(db, 8, EnrollmentCreate(certification_id=1)))

    pg_session(lambda db: enrollment_service.update_enrollment(
        db, 7, created["id"], EnrollmentUpdate(status="completed")))
    again = pg_session(lambda db: enrollment_service.create_enrollment(db, 7, EnrollmentCreate(certification_id=1)))
    assert again["id"] != created["id"]

    mine = pg_session(lambda db: enrollment_service.list_enrollments(db, 7))
    assert {e["status"] for e in mine} == {"active", "completed"}


@needs_db
def test_db_raw_insert_conflict_returns_none(pg_session) -> None:
    """The ON CONFLICT target really matches the partial index (no exception, just no row)."""

    async def twice(db):
        args = dict(user_id=7, certification_id=2, goal=None, deadline=None, weekly_study_hours=None)
        first = await repo.insert_open_enrollment(db, **args)
        second = await repo.insert_open_enrollment(db, **args)
        await db.commit()
        return first, second

    first, second = pg_session(twice)
    assert first is not None and second is None


@needs_db
def test_db_weekly_hours_trigger_maps_to_422(pg_session) -> None:
    """Bypass the service's own check so the database trigger has to catch it."""
    from fastapi import HTTPException

    pg_session(lambda db: enrollment_service.create_enrollment(
        db, 7, EnrollmentCreate(certification_id=1, weekly_study_hours=Decimal("100"))))

    async def no_precheck(db, user_id, exclude_enrollment_id=None):
        return Decimal(0)

    original = repo.open_hours_for_user
    repo.open_hours_for_user = no_precheck
    try:
        with pytest.raises(HTTPException) as exc:
            pg_session(lambda db: enrollment_service.create_enrollment(
                db, 7, EnrollmentCreate(certification_id=2, weekly_study_hours=Decimal("100"))))
    finally:
        repo.open_hours_for_user = original
    assert exc.value.status_code == 422


@needs_db
def test_db_patch_is_scoped_to_owner(pg_session) -> None:
    from fastapi import HTTPException

    created = pg_session(lambda db: enrollment_service.create_enrollment(db, 7, EnrollmentCreate(certification_id=1)))
    with pytest.raises(HTTPException) as exc:
        pg_session(lambda db: enrollment_service.update_enrollment(
            db, 8, created["id"], EnrollmentUpdate(status="abandoned")))
    assert exc.value.status_code == 404

    paused = pg_session(lambda db: enrollment_service.update_enrollment(
        db, 7, created["id"], EnrollmentUpdate(status="paused", goal="later")))
    assert paused["status"] == "paused" and paused["goal"] == "later"
