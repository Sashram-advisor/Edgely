"""Merged Edgely ASGI entry point.

Run this instead of ``app.main:app`` to get the original Edgely API plus the AI tutor:

    cd backend
    uvicorn app.merged_main:app --reload --port 8000

* Edgely's original app (``app.main:app``) is the host. Workstream A only added the
  ``/users`` router registration there; composition otherwise stays in this file.
* ``/tutor/*`` are the authenticated tutor routes (backend/app/routes/tutor.py).
* ``/ai-tutor/*`` is the tutor's own unauthenticated app. It is mounted only when APP_ENV=local AND
  ENABLE_LEGACY_TUTOR_MOUNT=true, because it trusts a user_id sent by the caller. The Streamlit dev UI uses it.
* ``/local-tutor/*`` is the optional offline Ollama bridge. It is also unauthenticated, so it is
  mounted only when APP_ENV=local AND ENABLE_LOCAL_TUTOR_MOUNT=true.

If the tutor cannot start (missing package or missing settings) Edgely still starts, the problem is
logged, and ``/health/tutor`` reports it.

T5 (Team A, P1): with APP_ENV=production (or development) ``/tutor`` is the ONLY tutor surface.
The two-switch rule above already keeps ``/ai-tutor`` and ``/local-tutor`` out; on top of that,
``_assert_single_tutor_surface()`` at the bottom of this file inspects the routes that were
actually registered and refuses to start if either unauthenticated surface slipped in
(for example through a future edit of this file). Fail closed: a crash at startup is better
than anonymous access to learner data.
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
    # Two switches, not one: local environment AND an explicit opt-in flag.
    # This keeps the unauthenticated tutor out of a misconfigured deployment
    # whose APP_ENV was accidentally left at "local".
    if settings.legacy_tutor_mount_enabled:
        app.mount("/ai-tutor", tutor_app, name="ai-tutor")
    tutor_ready = True
except Exception as exc:  # noqa: BLE001 - any failure must leave Edgely running
    tutor_error = f"{type(exc).__name__}: {exc}"
    log.exception("AI tutor is disabled")

# --- Offline Ollama tutor: local-only, opt-in ------------------------------------------------
# The local bridge has no authentication, so it is never mounted on a deployed server.
# Same two-switch rule as /ai-tutor: APP_ENV=local AND ENABLE_LOCAL_TUTOR_MOUNT=true.
if settings.local_tutor_mount_enabled:
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
    }
    if settings.local_tutor_mount_enabled:
        index["local_tutor_health"] = "/local-tutor/health"
    if tutor_ready:
        index["tutor_chat"] = "/tutor/chat"
        if settings.legacy_tutor_mount_enabled:
            index["ai_tutor_dev_docs"] = "/ai-tutor/docs"
    return index


# --- T5: only /tutor outside local development ----------------------------------------------
# Path prefixes of the tutor surfaces that have NO authentication.
UNAUTHENTICATED_TUTOR_PREFIXES = ("/ai-tutor", "/local-tutor")


def registered_paths() -> set[str]:
    """Every path the app will actually serve.

    ``app.routes`` shows mounts (``/ai-tutor``); the OpenAPI document shows
    included routers, which FastAPI 0.162 resolves lazily (``/local-tutor/...``).
    Reading both covers both ways a surface can be attached.
    """
    paths = {getattr(route, "path", "") for route in app.routes}
    paths |= set(app.openapi()["paths"])
    # openapi() caches its result; clear it so the real schema is rebuilt on the
    # first /openapi.json request and includes anything registered later.
    app.openapi_schema = None
    return paths


def _assert_single_tutor_surface() -> None:
    """Refuse to start a non-local server that exposes an unauthenticated tutor."""
    if settings.app_env == "local":
        return  # local developers may opt in to the legacy/offline tutors
    leaked = sorted(
        path for path in registered_paths() if path.startswith(UNAUTHENTICATED_TUTOR_PREFIXES)
    )
    if leaked:
        raise RuntimeError(
            f"APP_ENV={settings.app_env} must expose only /tutor, but unauthenticated tutor "
            f"routes are registered: {leaked}. Remove them or run with APP_ENV=local."
        )


# Runs once at import time, after every router above has been registered.
_assert_single_tutor_surface()
