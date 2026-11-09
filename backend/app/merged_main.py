"""Merged Edgely ASGI entry point.

Run this instead of ``app.main:app`` when you want the original Edgely API plus
both tutor implementations:

    cd backend
    uvicorn app.merged_main:app --reload --port 8000

What is composed here:

* Edgely's original app (``app.main:app``) is the host.  Its health endpoint,
  startup database check, CORS settings and future Edgely routers are unchanged.
* ``/ai-tutor`` is the untouched FastAPI app from ``services/ai_tutor``.
* ``/local-tutor`` is an additive bridge to ``services/local_tutor`` (the zip),
  which talks to a local Ollama daemon.

No existing Edgely source file is edited by this module.  The mounts are added
to the imported app object at process start, which keeps the original
``uvicorn app.main:app`` behaviour available for the Edgely-only deployment.
"""

from __future__ import annotations

from app.integrations.ai_tutor_mount import get_ai_tutor_app
from app.integrations.local_tutor_api import router as local_tutor_router
from app.main import app

# Keep the AI Tutor app's own paths (it contains /chat, /users, ...) and expose
# them under a namespace so they cannot collide with future Edgely routes.
app.mount("/ai-tutor", get_ai_tutor_app(), name="ai-tutor")

# The bridge is a normal router, so its OpenAPI schema appears in the merged
# app's /docs page alongside Edgely's routes.
app.include_router(local_tutor_router, prefix="/local-tutor", tags=["local-tutor"])


@app.get("/", include_in_schema=False)
def merged_service_index() -> dict[str, object]:
    """Small discovery document for the merged service."""

    return {
        "service": "Edgely merged API",
        "edgely_health": "/health",
        "edgely_docs": "/docs",
        "ai_tutor": "/ai-tutor",
        "ai_tutor_docs": "/ai-tutor/docs",
        "local_tutor_health": "/local-tutor/health",
        "local_tutor_chat": "/local-tutor/chat",
    }
