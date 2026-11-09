"""Standalone entry point for the local Ollama tutor.

Useful when you want to exercise the functionality from ``Ai Tutor.zip`` without
a Supabase/Postgres instance or cloud API keys.  It exposes only the additive
``/local-tutor`` bridge and does not import Edgely's database-backed app.

    cd backend
    uvicorn app.local_only_main:app --reload --port 8001

Then run the merged UI against it; the *Local Ollama* mode works, while the
course mode correctly reports that `/ai-tutor` is unavailable.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.integrations.local_tutor_api import router as local_tutor_router

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
