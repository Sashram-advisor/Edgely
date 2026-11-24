"""Standalone entry point for the local Ollama tutor.

Useful when you want to exercise the functionality from ``Ai Tutor.zip`` without
a Supabase/Postgres instance or cloud API keys.  It exposes only the additive
``/local-tutor`` bridge and does not import Edgely's database-backed app.

    cd backend
    APP_ENV=local uvicorn app.local_only_main:app --reload --port 8001

Then run the merged UI against it; the *Local Ollama* mode works, while the
course mode correctly reports that `/ai-tutor` is unavailable.

T5 (Team A, P1): ``/local-tutor`` has no authentication, so this entry point
refuses to start unless ``APP_ENV=local``. Without that check, anyone who ran
``uvicorn app.local_only_main:app`` on a server would publish an anonymous tutor.
``APP_ENV`` is read straight from the environment (not from ``app.core.config``)
because importing Edgely's settings would require ``DATABASE_URL``, which this
entry point deliberately does not need.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.integrations.local_tutor_api import router as local_tutor_router

# Same default as app.core.config.Settings.app_env: production unless told otherwise.
_APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
if _APP_ENV != "local":
    raise RuntimeError(
        "app.local_only_main serves the unauthenticated /local-tutor bridge and only runs with "
        f"APP_ENV=local (got APP_ENV={_APP_ENV!r}). Use app.merged_main:app for any shared server."
    )

app = FastAPI(title="Edgely Local Ollama Tutor")
app.include_router(local_tutor_router, prefix="/local-tutor", tags=["local-tutor"])


@app.get("/", include_in_schema=False)
def local_only_index() -> dict[str, str]:
    return {
        "service": "Edgely local Ollama tutor",
        "health": "/local-tutor/health",
        "chat": "/local-tutor/chat",
        "docs": "/docs",
    }
