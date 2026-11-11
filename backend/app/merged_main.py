"""Merged Edgely ASGI entry point.

Run this instead of ``app.main:app`` to get the original Edgely API plus the AI tutor:

    cd backend
    uvicorn app.merged_main:app --reload --port 8000

* Edgely's original app (``app.main:app``) is the host and is not edited.
* ``/tutor/*`` are the authenticated tutor routes (backend/app/routes/tutor.py).
* ``/ai-tutor/*`` is the tutor's own unauthenticated app. It is mounted only when APP_ENV=local,
  because it trusts a user_id sent by the caller. The Streamlit dev UI uses it.
* ``/local-tutor/*`` is the optional offline Ollama bridge.

If the tutor cannot start (missing package or missing settings) Edgely still starts, the problem is
logged, and ``/health/tutor`` reports it.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.integrations.local_tutor_api import router as local_tutor_router
from app.main import app

log = logging.getLogger("edgely.merged")

# --- AI tutor: start it safely -----------------------------------------------------------------
tutor_ready = False
tutor_error: str | None = None
try:
    from app.integrations.ai_tutor_mount import get_ai_tutor_app
    from app.routes import tutor as tutor_routes

    tutor_app = get_ai_tutor_app()

    # Fail now, with a clear message, if SUPABASE_URL or SUPABASE_SECRET_KEY is missing.
    from edgely_ai_tutor.config import get_settings as _tutor_settings

    _tutor_settings()

    app.include_router(tutor_routes.router, prefix="/tutor", tags=["tutor"])
    if settings.app_env == "local":
        app.mount("/ai-tutor", tutor_app, name="ai-tutor")
    tutor_ready = True
except Exception as exc:  # noqa: BLE001 - any failure must leave Edgely running
    tutor_error = f"{type(exc).__name__}: {exc}"
    log.exception("AI tutor is disabled")

app.include_router(local_tutor_router, prefix="/local-tutor", tags=["local-tutor"])


@app.get("/health/tutor")
def tutor_health() -> dict[str, str]:
    """ok = settings loaded and the pgvector migration is applied. Never raises."""
    if not tutor_ready:
        # Full text only in local development. It can name settings, so keep it off public servers.
        detail = tutor_error or "unknown"
        return {"status": "disabled", "detail": detail if settings.app_env == "local" else detail.split(":")[0]}
    try:
        from edgely_ai_tutor.db import get_db

        get_db().table("document_chunks").select("embedding_model").limit(1).execute()
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: migration or Supabase problem"}


@app.get("/", include_in_schema=False)
def merged_service_index() -> dict[str, object]:
    index: dict[str, object] = {
        "service": "Edgely merged API",
        "edgely_health": "/health",
        "tutor_health": "/health/tutor",
        "edgely_docs": "/docs",
        "tutor_enabled": tutor_ready,
        "local_tutor_health": "/local-tutor/health",
    }
    if tutor_ready:
        index["tutor_chat"] = "/tutor/chat"
        if settings.app_env == "local":
            index["ai_tutor_dev_docs"] = "/ai-tutor/docs"
    return index