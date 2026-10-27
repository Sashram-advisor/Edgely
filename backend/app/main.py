"""main.py - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import check_connection, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fail early if the database is unreachable
    if not await check_connection():
        raise RuntimeError("Cannot connect to the database. Check DATABASE_URL in .env")
    yield
    # Shutdown: release pooled connections
    await close_db()


app = FastAPI(title="Sashram Agentic AI Certification Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers here as they are built, e.g.:
# from routers import chat, quizzes, dashboard, enrollments, documents
# app.include_router(chat.router, prefix="/chat", tags=["chat"])


@app.get("/health")
async def health():
    return {"status": "ok" if await check_connection() else "database_unreachable"}
