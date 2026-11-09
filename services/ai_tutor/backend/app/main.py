"""FastAPI routes. Thin layer: validation and HTTP status mapping; the logic lives in chat.py / context.py.

    uvicorn backend.app.main:app --reload
    ENV_FILE=.env.test uvicorn backend.app.main:app --reload   # local Supabase
"""
import json
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .chat import ChatRequest, ConversationNotFound, NotEnrolled, chat_turn, prepare_turn, stream_turn
from .context import UserNotFound, load_learner_context
from .db import get_db

app = FastAPI(title="AI Tutor")


@app.exception_handler(UserNotFound)
async def _user_not_found(_: Request, exc: UserNotFound):
    return JSONResponse(status_code=404, content={"detail": f"User {exc} not found"})


@app.exception_handler(ConversationNotFound)
async def _conversation_not_found(_: Request, exc: ConversationNotFound):
    return JSONResponse(status_code=404, content={"detail": f"Conversation {exc} not found"})


@app.exception_handler(NotEnrolled)
async def _not_enrolled(_: Request, exc: NotEnrolled):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


class ChatBody(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = None
    certification_id: int | None = None


@app.post("/chat")
def chat(body: ChatBody) -> dict:
    return chat_turn(ChatRequest(**body.model_dump()))


@app.post("/chat/stream")
def chat_stream(body: ChatBody) -> StreamingResponse:
    # Prepare first, so 403/404 come back as normal HTTP errors before the stream starts.
    prep = prepare_turn(ChatRequest(**body.model_dump()))

    def events():
        yield _sse("meta", {"conversation_id": prep.conversation_id, "standalone_query": prep.standalone_query})
        try:
            for kind, payload in stream_turn(prep):
                yield _sse(kind, {"text": payload} if kind == "delta" else payload)
        except Exception as e:  # headers are already sent; report the failure in-band
            yield _sse("error", {"detail": str(e)})

    return StreamingResponse(events(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/users")
def list_users() -> list[dict]:
    return get_db().table("users").select("id,display_name,email,role").eq("role", "learner").order("id").execute().data


@app.get("/users/{user_id}/context")
def user_context(user_id: int) -> dict:
    return asdict(load_learner_context(user_id))


@app.get("/users/{user_id}/conversations")
def user_conversations(user_id: int) -> list[dict]:
    return (
        get_db()
        .table("conversations")
        .select("id,title,certification_id,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data
    )


@app.get("/conversations/{conversation_id}/messages")
def conversation_messages(conversation_id: int, user_id: int) -> list[dict]:
    db = get_db()
    conv = db.table("conversations").select("user_id").eq("id", conversation_id).execute().data
    if not conv or conv[0]["user_id"] != user_id:
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
