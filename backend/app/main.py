"""main.py - FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import check_connection, close_db
from app.routes import users as users_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fail early if the database is unreachable
    if not await check_connection():
        raise RuntimeError("Cannot connect to the database. Check DATABASE_URL in .env")
    yield
    # Shutdown: release pooled connections
    await close_db()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers here as they are built. Each router owns its own prefix and
# tags so this file stays a thin composition root.
app.include_router(users_routes.router)
app.include_router(certifications.router)
app.include_router(enrollments.router)


@app.get("/health")
async def health():
    return {"status": "ok" if await check_connection() else "database_unreachable"}
