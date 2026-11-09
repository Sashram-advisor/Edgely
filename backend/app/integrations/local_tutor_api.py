"""HTTP bridge for the local Ollama tutor (the code from ``Ai Tutor.zip``).

The original zip is a terminal program: it loads ``data/study_material.txt``,
embeds each section with ``nomic-embed-text``, ranks sections by cosine
similarity and asks ``llama3.2:3b`` to answer from the retrieved text.

The original files are kept untouched in ``services/local_tutor`` and remain
runnable as a CLI.  This module is a new, additive adapter that exposes the same
functionality to the merged Edgely API.  It intentionally follows the original
prompt and retrieval approach, with one usability improvement: the bundled
material uses ``Topic N:`` headings (the original splitter looked for ``##``),
so both heading styles are recognised.  The CLI itself is unchanged and still
uses its original splitter.

Configuration is environment-only so no secret enters the repository.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MATERIAL = _REPO_ROOT / "services" / "local_tutor" / "data" / "study_material.txt"

# The zip's splitter was ``re.split(r"\n(?=## )", material)``.  Its bundled
# material uses "Topic N:" headings instead, which produced one giant section.
# Recognising both keeps the same input format usable without touching the
# original script.
_SECTION_BOUNDARY = re.compile(r"\n(?=(?:## |Topic \d+:))")

_SYSTEM_INSTRUCTIONS = """\
You are an AWS Certified Cloud Practitioner tutor. Answer using only the \
relevant study material below. If the material does not contain enough \
information to answer, say that the topic is not covered in the provided \
material. Do not invent facts or claim unsupported information came from the \
material. Explain concepts clearly and use examples from the material when \
helpful.

RELEVANT STUDY MATERIAL:
"""


@dataclass(frozen=True)
class LocalTutorSettings:
    material_path: Path
    ollama_base_url: str
    embed_model: str
    chat_model: str
    timeout_seconds: float
    max_sections: int


@lru_cache(maxsize=1)
def get_settings() -> LocalTutorSettings:
    return LocalTutorSettings(
        material_path=Path(os.getenv("LOCAL_TUTOR_MATERIAL", str(_DEFAULT_MATERIAL))),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        chat_model=os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:3b"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
        max_sections=int(os.getenv("LOCAL_TUTOR_MAX_SECTIONS", "2")),
    )


@lru_cache(maxsize=4)
def load_material(path: str) -> str:
    material_path = Path(path)
    if not material_path.is_file():
        raise FileNotFoundError(f"Local tutor material not found: {material_path}")
    return material_path.read_text(encoding="utf-8")


def split_sections(material: str) -> list[str]:
    """Split the AWS study material into topic-sized retrieval units."""

    sections = _SECTION_BOUNDARY.split(material)
    return [section.strip() for section in sections if section.strip()]


def section_title(section: str) -> str:
    first_line = section.splitlines()[0].strip() if section.splitlines() else "Study material"
    return first_line[:120]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity, implemented without adding a numpy dependency."""

    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    denominator = left_norm * right_norm
    if denominator == 0:
        return 0.0
    return dot / denominator


class LocalChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    max_sections: int | None = Field(default=None, ge=1, le=8)


class LocalSource(BaseModel):
    source_id: str
    title: str
    similarity: float


class LocalChatResponse(BaseModel):
    answer: str
    model: str
    sources: list[LocalSource]
    material: str
    sections_available: int


class LocalHealthResponse(BaseModel):
    status: str
    material: str
    sections: int
    embed_model: str
    chat_model: str
    ollama_reachable: bool


def _ollama_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}{path}",
            json=payload,
            timeout=settings.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Ollama is not reachable at {settings.ollama_base_url}. "
                "Start Ollama and pull the configured models, then retry. "
                f"Underlying error: {exc}"
            ),
        ) from exc


def embed_text(text: str) -> list[float]:
    settings = get_settings()
    payload = _ollama_post(
        "/api/embeddings",
        {"model": settings.embed_model, "prompt": text},
    )
    embedding = payload.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise HTTPException(status_code=502, detail="Ollama returned an empty embedding")
    return [float(value) for value in embedding]


def retrieve_sections(question: str, max_sections: int | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    material = load_material(str(settings.material_path))
    sections = split_sections(material)
    if not sections:
        raise HTTPException(status_code=500, detail="Local tutor material is empty")

    question_embedding = embed_text(question)
    scored: list[dict[str, Any]] = []
    for section in sections:
        score = cosine_similarity(question_embedding, embed_text(section))
        scored.append({"title": section_title(section), "content": section, "similarity": score})

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    limit = max_sections or settings.max_sections
    return scored[:limit]


def _ollama_reachable() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        return response.is_success
    except httpx.HTTPError:
        return False


@router.get("/health", response_model=LocalHealthResponse)
def local_health() -> LocalHealthResponse:
    settings = get_settings()
    try:
        material = load_material(str(settings.material_path))
        sections = len(split_sections(material))
        material_name = str(settings.material_path)
    except FileNotFoundError:
        sections = 0
        material_name = str(settings.material_path)

    return LocalHealthResponse(
        status="ok" if sections else "material_missing",
        material=material_name,
        sections=sections,
        embed_model=settings.embed_model,
        chat_model=settings.chat_model,
        ollama_reachable=_ollama_reachable(),
    )


@router.get("/material")
def local_material() -> dict[str, Any]:
    settings = get_settings()
    try:
        material = load_material(str(settings.material_path))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    sections = split_sections(material)
    return {
        "path": str(settings.material_path),
        "characters": len(material),
        "sections": [{"title": section_title(s), "characters": len(s)} for s in sections],
    }


@router.post("/chat", response_model=LocalChatResponse)
def local_chat(body: LocalChatRequest) -> LocalChatResponse:
    settings = get_settings()
    sources = retrieve_sections(body.message, body.max_sections)
    relevant_material = "\n\n".join(source["content"] for source in sources)

    payload = _ollama_post(
        "/api/chat",
        {
            "model": settings.chat_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": _SYSTEM_INSTRUCTIONS + relevant_material},
                {"role": "user", "content": body.message},
            ],
            "options": {"temperature": 0.2},
        },
    )

    try:
        answer = payload["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Ollama returned an unexpected chat response") from exc

    return LocalChatResponse(
        answer=answer,
        model=settings.chat_model,
        sources=[
            LocalSource(
                source_id=f"S{index}",
                title=source["title"],
                similarity=round(source["similarity"], 4),
            )
            for index, source in enumerate(sources, start=1)
        ],
        material=settings.material_path.name,
        sections_available=len(split_sections(load_material(str(settings.material_path)))),
    )
