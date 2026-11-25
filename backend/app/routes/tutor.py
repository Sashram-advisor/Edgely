"""Authenticated AI tutor routes.

The learner is identified from the verified login token, never from the request body.
The tutor logic itself still lives in services/ai_tutor and is called, not copied.

P1 changes (Team A):
* T3 - the stream's ``error`` event no longer contains exception text. It carries a
  stable code instead (core/tutor_sse.py; contract in docs/api/tutor-sse.md).
* T4 - ``/chat`` and ``/chat/stream`` are rate-limited per learner
  (core/rate_limit.py): too many questions -> 429 with a Retry-After header.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.dependencies import current_user_id
from app.core.rate_limit import enforce_tutor_rate_limit
from app.core.tutor_sse import EVENT_DELTA, EVENT_META, error_event_for, format_event
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


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    certification_id: int | None = None


# These are plain `def` routes on purpose: FastAPI runs them in a worker thread,
# which suits the tutor's blocking Supabase and Claude clients.


@router.post("/chat")
def chat(body: ChatBody, user_id: int = Depends(enforce_tutor_rate_limit)) -> dict:
    # enforce_tutor_rate_limit (T4) resolves the verified user id AND counts this
    # question against the learner's limit; it raises 429 before any model call.
    tutor_chat, _, _ = _tutor()
    with tutor_errors():
        return tutor_chat.chat_turn(tutor_chat.ChatRequest(user_id=user_id, **body.model_dump()))


@router.post("/chat/stream")
def chat_stream(body: ChatBody, user_id: int = Depends(enforce_tutor_rate_limit)) -> StreamingResponse:
    """Stream one tutor answer as Server-Sent Events.

    Wire format (docs/api/tutor-sse.md): ``meta`` once, ``delta`` 0..n times,
    then exactly one of ``done`` or ``error``. Failures that happen *before* the
    stream starts (401/403/404/422/429) are ordinary HTTP errors.
    """
    tutor_chat, _, _ = _tutor()
    with tutor_errors():
        # Prepare first so 403/404 come back as normal HTTP errors before streaming starts.
        prep = tutor_chat.prepare_turn(tutor_chat.ChatRequest(user_id=user_id, **body.model_dump()))

    def events():
        yield format_event(EVENT_META, {"conversation_id": prep.conversation_id, "standalone_query": prep.standalone_query})
        try:
            for kind, payload in tutor_chat.stream_turn(prep):
                # stream_turn yields ("delta", str) and finally ("done", dict).
                yield format_event(kind, {"text": payload} if kind == EVENT_DELTA else payload)
        except Exception as exc:  # noqa: BLE001 - headers are already sent, so report in-band
            # T3: log the real exception server-side; send only a stable code to the client.
            yield error_event_for(exc, user_id=user_id, conversation_id=prep.conversation_id)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        # Stop proxies (nginx, some CDNs) from buffering the whole answer, which
        # would turn the live stream into one late response.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
