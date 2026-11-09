"""Embeddings via Gemini or OpenAI, selected by EMBEDDING_PROVIDER.

Vectors from different models are not comparable: after switching provider/model,
re-run scripts/embed_chunks.py to re-embed every chunk.
"""
import time
from functools import lru_cache

from .config import get_settings

BATCH_SIZE = 100


@lru_cache
def _gemini_client():
    from google import genai

    return genai.Client(api_key=get_settings().gemini_api_key)


@lru_cache
def _openai_client():
    from openai import OpenAI

    return OpenAI(api_key=get_settings().openai_api_key)


def _embed_batch(texts: list[str], task_type: str) -> list[list[float]]:
    s = get_settings()
    if s.embedding_provider == "gemini":
        from google.genai import types

        resp = _gemini_client().models.embed_content(
            model=s.embedding_model,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=s.embedding_dim),
        )
        return [e.values for e in resp.embeddings]

    resp = _openai_client().embeddings.create(model=s.embedding_model, input=texts, dimensions=s.embedding_dim)
    return [d.embedding for d in resp.data]


def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        for attempt in range(5):
            try:
                out.extend(_embed_batch(batch, task_type))
                break
            except Exception as e:  # free-tier rate limits surface as 429s
                if attempt == 4 or "429" not in str(e):
                    raise
                time.sleep(2**attempt * 5)
    return out


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text: str) -> list[float]:
    return _embed([text], "RETRIEVAL_QUERY")[0]
