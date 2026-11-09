"""Structural and pure-function checks for the merged codebase.

These tests are deliberately offline: they do not call Supabase, Claude, Gemini
or Ollama.  They catch the integration failures that are easy to introduce when
two FastAPI projects are composed (bad mount paths, broken relative imports,
missing migration clauses and broken retrieval helpers).
"""

from __future__ import annotations

import math
from pathlib import Path

from app.integrations.ai_tutor_mount import get_ai_tutor_app
from app.integrations.local_tutor_api import (
    cosine_similarity,
    load_material,
    split_sections,
)
from app.merged_main import app

ROOT = Path(__file__).resolve().parents[1]


def _route_paths() -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def test_edgely_routes_are_still_present() -> None:
    paths = _route_paths()
    assert "/health" in paths
    assert "/docs" in paths
    assert "/openapi.json" in paths


def test_ai_tutor_is_mounted() -> None:
    paths = _route_paths()
    assert "/ai-tutor" in paths
    assert get_ai_tutor_app().title == "AI Tutor"


def test_local_tutor_routes_are_registered() -> None:
    # FastAPI 0.162 represents an included router lazily in app.routes, so use
    # the generated OpenAPI document to observe the effective prefixed paths.
    paths = set(app.openapi()["paths"])
    assert "/local-tutor/health" in paths
    assert "/local-tutor/chat" in paths
    assert "/local-tutor/material" in paths


def test_local_only_entrypoint_is_usable_without_edgely_database() -> None:
    from app.local_only_main import app as local_only_app

    paths = set(local_only_app.openapi()["paths"])
    assert "/local-tutor/chat" in paths
    assert "/health" not in paths  # Edgely's DB-backed health is deliberately absent


def test_ai_tutor_relative_imports_survived_relocation() -> None:
    # Importing the app already proves this, but assert the public pieces the
    # Streamlit UI depends on are present.
    ai_tutor_app = get_ai_tutor_app()
    ai_paths = {getattr(route, "path", "") for route in ai_tutor_app.routes}
    assert "/chat" in ai_paths
    assert "/chat/stream" in ai_paths
    assert "/users" in ai_paths
    assert "/users/{user_id}/conversations" in ai_paths
    assert "/conversations/{conversation_id}/messages" in ai_paths


def test_zip_material_is_split_into_topics() -> None:
    material = load_material(str(ROOT / "services" / "local_tutor" / "data" / "study_material.txt"))
    sections = split_sections(material)
    assert len(sections) >= 5
    assert any(section.startswith("Topic 1:") for section in sections)
    assert any(section.startswith("Topic 2:") for section in sections)
    assert all(len(section) > 40 for section in sections)


def test_cosine_similarity_math() -> None:
    assert math.isclose(cosine_similarity([1.0, 0.0], [1.0, 0.0]), 1.0)
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_ai_tutor_citation_parser() -> None:
    # The vendored package is registered under a private name by
    # get_ai_tutor_app(), so it cannot collide with Edgely's backend/ directory.
    from edgely_ai_tutor.prompt import cited_source_indexes

    assert cited_source_indexes("[S2] first, then [S1] and [S9].", 3) == [1, 0]
    assert cited_source_indexes("no citations", 3) == []


def test_pgvector_migration_has_the_required_additions() -> None:
    migration = (
        ROOT
        / "backend"
        / "app"
        / "database"
        / "migrations"
        / "20261102000100_ai_tutor_pgvector.sql"
    ).read_text(encoding="utf-8")
    assert "create extension if not exists vector" in migration
    assert "add column if not exists embedding" in migration
    assert "add column if not exists similarity" in migration
    assert "add column if not exists rank" in migration
    assert "match_document_chunks" in migration
    assert "grant execute on function public.match_document_chunks to service_role" in migration
