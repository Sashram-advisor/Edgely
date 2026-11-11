"""Settings loaded from .env, optionally overridden by ENV_FILE (e.g. ENV_FILE=.env.test for local Supabase)."""
import os
from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_files = tuple(f for f in (".env", os.getenv("ENV_FILE")) if f)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files, extra="ignore")

    supabase_url: str
    supabase_secret_key: str

    embedding_provider: Literal["gemini", "openai"] = "gemini"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 1536  # must match document_chunks.embedding vector(1536)
    gemini_api_key: str | None = None
    openai_api_key: str | None = None

    # Chat runs on Claude; Haiku is the cheapest model, fine for testing. Switch to claude-sonnet-5-5 for quality.
    anthropic_api_key: str | None = Field(None, validation_alias=AliasChoices("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"))
    chat_model: str = "claude-haiku-4-5"
    rewrite_model: str = "claude-haiku-4-5"
    max_answer_tokens: int = 1024

    # Retrieval: relevant chunks score ~0.6-0.74 with Gemini, off-topic ~0.46. Tune with eval/run_eval.py.
    retrieval_k: int = 6
    min_similarity: float = 0.55
    history_messages: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
