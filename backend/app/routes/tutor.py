"""Authenticated AI tutor routes.

The learner is identified from the verified login token, never from the request body.
The tutor logic itself still lives in services/ai_tutor and is called, not copied.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_provider import AuthenticatedUser, get_current_auth_user
from app.core.db import fetch_one, get_db
from app.integrations.ai_tutor_mount import get_ai_tutor_app

router = APIRouter()


def _tutor():
    """Load the private edgely_ai_tutor package and return the modules we call."""
    get_ai_tutor_app()
    from edgely_ai_tutor import chat, context, db

    return chat, context, db


@contextmanager
def tutor_errors():
    """Turn the tutor's own exceptions into normal HTTP errors."""
    chat, context, _ = _tutor()
    try:
        yield
    except chat.NotEnrolled as exc:
        raise HTTPException(403, str(exc)) from exc
    except chat.ConversationNotFound as exc:
        raise HTTPException(404, f"Conversation {exc} not found") from exc
    except context.UserNotFound as exc:
        raise HTTPException(404, f"User {exc} not found") from exc


async def current_user_id(
    auth: AuthenticatedUser = Depends(get_current_auth_user),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Map the verified login to users.id. This is the only source of the user id."""
    row = await fetch_one(
        db,
        "SELECT id FROM users WHERE external_auth_id = :auth_id",
        {"auth_id": auth.auth_id},
    )
    if row is None:
        raise HTTPException(403, "No platform user exists for this login")
    return row["id"]


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    certification_id: int | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# These are plain `def` routes on purpose: FastAPI runs them in a worker thread,
# which suits the tutor's blocking Supabase and Claude clients.


@router.post("/chat")
def chat(body: ChatBody, user_id: int = Depends(current_user_id)) -> dict:
    tutor_chat, _, _ = _tutor()
    with tutor_errors():
        return tutor_chat.chat_turn(tutor_chat.ChatRequest(user_id=user_id, **body.model_dump()))


@router.post("/chat/stream")
def chat_stream(body: ChatBody, user_id: int = Depends(current_user_id)) -> StreamingResponse:
    tutor_chat, _, _ = _tutor()
    with tutor_errors():
        # Prepare first so 403/404 come back as normal HTTP errors before streaming starts.
        prep = tutor_chat.prepare_turn(tutor_chat.ChatRequest(user_id=user_id, **body.model_dump()))

    def events():
        yield _sse("meta", {"conversation_id": prep.conversation_id, "standalone_query": prep.standalone_query})
        try:
            for kind, payload in tutor_chat.stream_turn(prep):
                yield _sse(kind, {"text": payload} if kind == "delta" else payload)
        except Exception as exc:  # headers are already sent, so report the failure in the stream
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


@router.get("/me/context")
def my_context(user_id: int = Depends(current_user_id)) -> dict:
    _, tutor_context, _ = _tutor()
    with tutor_errors():
        return asdict(tutor_context.load_learner_context(user_id))


@router.get("/conversations")
def my_conversations(user_id: int = Depends(current_user_id)) -> list[dict]:
    _, _, tutor_db = _tutor()
    return (
        tutor_db.get_db()
        .table("conversations")
        .select("id,title,certification_id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, user_id: int = Depends(current_user_id)) -> list[dict]:
    _, _, tutor_db = _tutor()
    db = tutor_db.get_db()
    owner = db.table("conversations").select("user_id").eq("id", conversation_id).execute().data
    if not owner or owner[0]["user_id"] != user_id:
        raise HTTPException(404, f"Conversation {conversation_id} not found")
    return (
        db.table("messages")
        .select(
            "id,role,content,model,created_at,"
            "message_citations!message_citations_message_id_fkey(chunk_id,similarity,rank,"
            "document_chunks!message_citations_chunk_id_fkey(metadata,documents!document_chunks_document_id_fkey(title)))"
        )
        .eq("conversation_id", conversation_id)
        .in_("role", ["user", "assistant"])
        .order("id")
        .execute()
        .data
    )