"""config.py - Central application configuration (loaded from environment / .env).

Based on the teammate config: database_url, db_echo, openai_api_key, cors_origins.
Other modules import `settings` from here. Secrets stay in backend/.env.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/ directory. The real .env lives here, not next to this file.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Values read from the environment. Nothing in this class is a secret."""

    model_config = SettingsConfigDict(
        env_file=(_BACKEND_ROOT / ".env", Path(".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["local", "development", "production"] = "local"
    app_name: str = "Sashram Agentic AI Certification Platform"

    # Supabase PostgreSQL connection string (never commit the real value).
    # db.py reads database_url and the pool settings below.
    database_url: str
    db_echo: bool = False
    # Raise the pool in production without changing this file.
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_recycle_seconds: int = 1800
    # Supabase's pooler rejects prepared statements. 0 turns that cache off.
    db_statement_cache_size: int = 0

    # Supabase Auth (used by core/auth_provider.py to verify login tokens)
    supabase_url: str | None = None
    # Only needed if your project signs tokens with the older shared secret (HS256).
    supabase_jwt_secret: str | None = None

    # AI team: fill these in backend/.env. Leave them blank until your code reads them.
    # Import `settings` from this module. The files below are still empty.
    #
    # Tutor replies
    #   ai/language_model/azure_openai.py  reads the Azure OpenAI settings
    #   ai/agents/tutor/graph.py           builds the tutor workflow
    #   ai/agents/tutor/nodes.py           one step of that workflow
    #   ai/agents/tutor/tools.py           get_learner_context, search_knowledge, get_quiz_question
    # Direct OpenAI, from the teammate config. Use this if you do not use Azure.
    openai_api_key: str | None = None
    tutor_model: str = "gpt-4o-mini"
    # Azure OpenAI. Fill these if ai/language_model/azure_openai.py calls Azure.
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str | None = None
    azure_openai_deployment: str | None = None
    #
    # Retrieval. Pick one store in ai/knowledge_retrieval/vector_store/.
    #   retriever.py              calls the store from the tutor tools
    #   pgvector_store.py         embeddings in this same database (DATABASE_URL)
    #   azure_search_store.py     Azure AI Search; fill the three settings below
    #   chunking.py               splits a document before it is embedded
    azure_search_endpoint: str | None = None
    azure_search_api_key: str | None = None
    azure_search_index: str | None = None

    # Allowed frontend origins for CORS (Next.js dev server by default).
    # main.py passes this list to CORSMiddleware.
    # .env may use a comma-separated list or a JSON list.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if value is None or value == "":
            return ["http://localhost:3000"]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator(
        "openai_api_key",
        "azure_openai_endpoint",
        "azure_openai_api_key",
        "azure_openai_api_version",
        "azure_openai_deployment",
        "azure_search_endpoint",
        "azure_search_api_key",
        "azure_search_index",
        mode="before",
    )
    @classmethod
    def blank_string_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
