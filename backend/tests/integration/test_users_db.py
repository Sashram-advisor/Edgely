"""/users/me SQL against a real Postgres. Skipped unless EDGELY_TEST_DATABASE_URL is set."""

from __future__ import annotations

from app.schemas.user import UserUpdate
from app.services import user_service


def test_provision_is_idempotent_and_creates_the_profile(run_db) -> None:
    first = run_db(lambda db: user_service.provision_user(db, "auth-1", email="maya@example.com"))
    second = run_db(lambda db: user_service.provision_user(db, "auth-1", email="maya@example.com"))
    assert first["id"] == second["id"]
    assert first["display_name"] == "maya"
    assert first["role"] == "learner"

    async def counts(db):
        from app.core.db import fetch_one

        users = await fetch_one(db, "SELECT count(*) AS n FROM users")
        profiles = await fetch_one(db, "SELECT count(*) AS n FROM learner_profiles")
        return users["n"], profiles["n"]

    assert run_db(counts) == (1, 1)


def test_login_without_email_keeps_the_real_email(run_db) -> None:
    run_db(lambda db: user_service.provision_user(db, "auth-1", email="maya@example.com"))
    again = run_db(lambda db: user_service.provision_user(db, "auth-1", email=None))
    assert again["email"] == "maya@example.com"


def test_display_name_from_body_only_names_new_users(run_db) -> None:
    created = run_db(lambda db: user_service.provision_user(db, "auth-1", email="m@example.com", display_name="Maya"))
    again = run_db(lambda db: user_service.provision_user(db, "auth-1", email="m@example.com", display_name="Other"))
    assert created["display_name"] == again["display_name"] == "Maya"


def test_patch_works_for_a_user_without_a_profile_row(run_db, seed_sql) -> None:
    seed_sql(
        "INSERT INTO users (id, external_auth_id, display_name, email, role) "
        "VALUES (50, 'seed-50', 'Seed', 'seed@example.com', 'learner')"
    )
    updated = run_db(lambda db: user_service.update_user(db, 50, UserUpdate(weekly_study_hours=6)))
    assert updated["weekly_study_hours"] == 6
