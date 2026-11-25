"""One chat turn: context -> scope -> conversation -> rewrite -> retrieve -> prompt -> generate -> persist.

prepare_turn() does everything that can fail before we pay for generation (404/403s happen here).
stream_turn() streams the answer and persists it once complete. chat_turn() is the non-streaming wrapper.

T4 (Team A, P1):
* The query-rewrite call is skipped when the message does not look like a follow-up
  (needs_rewrite, controlled by REWRITE_MODE), so most turns make one model call, not two.
* Token usage of BOTH calls is recorded per turn: the assistant message row stores the
  turn total in tokens_in / tokens_out, the `done` payload breaks it down, and one
  structured log line per turn is written to the "edgely.tutor.usage" logger.
"""
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import lru_cache

import anthropic

from . import prompt
from .config import get_settings
from .context import LearnerContext, load_learner_context
from .db import get_db
from .retrieval import retrieve

usage_log = logging.getLogger("edgely.tutor.usage")


class ConversationNotFound(Exception):
    pass


class NotEnrolled(Exception):
    """The user isn't actively enrolled in the requested certification (or in anything)."""


@dataclass
class ChatRequest:
    user_id: int
    message: str
    conversation_id: int | None = None
    certification_id: int | None = None


@dataclass
class PreparedTurn:
    conversation_id: int
    message: str
    standalone_query: str
    cert_ids: list[int]
    sources: list[dict]
    domain_names: dict[int, str]
    system: list[dict]
    messages: list[dict]
    # T4: tokens spent by the rewrite call (both 0 when the rewrite was skipped).
    rewrite_usage: "RewriteUsage" = field(default_factory=lambda: RewriteUsage())
    user_id: int | None = None


@dataclass
class RewriteUsage:
    """Token counts of the optional query-rewrite call (T4)."""

    input_tokens: int = 0
    output_tokens: int = 0
    called: bool = False


@lru_cache
def _claude() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


# --- Step 2: scope -------------------------------------------------------------------------------

def resolve_scope(ctx: LearnerContext, conversation: dict | None, requested_cert_id: int | None) -> list[int]:
    """Pick which certification(s) to search. Raises NotEnrolled for anything not actively enrolled."""
    active = ctx.active_cert_ids
    explicit = (conversation or {}).get("certification_id") or requested_cert_id
    if explicit is not None:
        if explicit not in active:
            raise NotEnrolled(f"user {ctx.user_id} is not actively enrolled in certification {explicit}")
        return [explicit]
    if ctx.target_certification_id in active:
        return [ctx.target_certification_id]
    if not active:
        raise NotEnrolled(f"user {ctx.user_id} has no active enrollments")
    return active


# --- Step 3: conversation ------------------------------------------------------------------------

def _load_conversation(conversation_id: int, user_id: int) -> dict:
    rows = get_db().table("conversations").select("*").eq("id", conversation_id).execute().data
    # Someone else's conversation is reported as missing, so ids can't be probed.
    if not rows or rows[0]["user_id"] != user_id:
        raise ConversationNotFound(conversation_id)
    return rows[0]


def _create_conversation(user_id: int, cert_ids: list[int], message: str) -> int:
    row = {
        "user_id": user_id,
        "certification_id": cert_ids[0] if len(cert_ids) == 1 else None,
        "title": message.strip()[:60],
    }
    return get_db().table("conversations").insert(row).execute().data[0]["id"]


def load_history(conversation_id: int, limit: int) -> list[dict]:
    """Last `limit` user/assistant messages, oldest first. Seeded 'system' rows are skipped."""
    rows = (
        get_db()
        .table("messages")
        .select("role,content")
        .eq("conversation_id", conversation_id)
        .in_("role", ["user", "assistant"])
        .order("id", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    # The API requires the first message to be from the user.
    while history and history[0]["role"] != "user":
        history.pop(0)
    return history


# --- Step 4: rewrite -----------------------------------------------------------------------------

# Words that usually point back at something said earlier in the conversation.
# If a message contains one of these, retrieval on the raw text would probably
# miss the real topic, so it is worth paying for a rewrite.
_FOLLOW_UP_WORDS = {
    "it", "its", "it's", "this", "that", "these", "those", "they", "them", "their",
    "he", "she", "him", "her", "one", "ones", "above", "previous", "earlier", "same",
    "else", "more", "again", "also", "instead", "former", "latter",
}
# Openings that are follow-ups even without a pronoun ("what about Glacier?", "and S3?").
_FOLLOW_UP_OPENINGS = ("what about", "how about", "and ", "but ", "or ", "why not", "then ", "so ")
# A message this short is rarely a full question on its own ("why?", "example please").
_MIN_STANDALONE_WORDS = 5
_WORD_RE = re.compile(r"[a-z']+")


def needs_rewrite(history: list[dict], message: str, mode: str = "auto") -> bool:
    """Decide whether the extra rewrite model call is worth it (T4).

    Pure function (no I/O) so it is easy to unit-test.

    * No history -> never: there is nothing to resolve (this was already true before T4).
    * mode "off" -> never.  mode "always" -> whenever there is history.
    * mode "auto" -> only when the message looks like a follow-up: very short,
      starts like "what about ...", or contains a back-referencing word.

    The heuristic errs on the side of rewriting: a false "yes" costs one cheap
    call (the pre-T4 behaviour); a false "no" could hurt retrieval quality.
    """
    if not history or mode == "off":
        return False
    if mode == "always":
        return True
    text = message.strip().lower()
    words = _WORD_RE.findall(text)
    if len(words) < _MIN_STANDALONE_WORDS:
        return True
    if text.startswith(_FOLLOW_UP_OPENINGS):
        return True
    return any(word in _FOLLOW_UP_WORDS for word in words)


def rewrite_query(history: list[dict], message: str, usage: RewriteUsage | None = None) -> str:
    """Turn a follow-up ("what about Glacier?") into a standalone question for retrieval.

    T4: when ``usage`` is given, the rewrite call's token counts are written into
    it, so the turn can record what it really cost.
    """
    if not history:
        return message
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    resp = _claude().messages.create(
        model=get_settings().rewrite_model,
        max_tokens=200,
        system=prompt.REWRITE_INSTRUCTIONS,
        messages=[
            {
                "role": "user",
                "content": f"<conversation>\n{transcript}\n</conversation>\n\nLatest message: {message}",
            }
        ],
    )
    if usage is not None:
        usage.called = True
        usage.input_tokens = resp.usage.input_tokens
        usage.output_tokens = resp.usage.output_tokens
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return text or message


# --- Steps 1-6 -----------------------------------------------------------------------------------

def prepare_turn(req: ChatRequest) -> PreparedTurn:
    s = get_settings()
    ctx = load_learner_context(req.user_id)                                     # 1
    conversation = _load_conversation(req.conversation_id, req.user_id) if req.conversation_id else None
    cert_ids = resolve_scope(ctx, conversation, req.certification_id)           # 2
    if conversation:                                                            # 3
        conversation_id = conversation["id"]
        history = load_history(conversation_id, s.history_messages)
    else:
        conversation_id = _create_conversation(req.user_id, cert_ids, req.message)
        history = []

    # 4. T4: only pay for the rewrite call when the message looks like a follow-up.
    rewrite_usage = RewriteUsage()
    if needs_rewrite(history, req.message, s.rewrite_mode):
        standalone = rewrite_query(history, req.message, rewrite_usage)
    else:
        standalone = req.message
    sources = retrieve(standalone, cert_ids)                                    # 5

    domain_ids = list({c["exam_domain_id"] for c in sources if c["exam_domain_id"]})
    domain_names = (
        {d["id"]: d["name"] for d in get_db().table("exam_domains").select("id,name").in_("id", domain_ids).execute().data}
        if domain_ids
        else {}
    )

    return PreparedTurn(                                                        # 6
        conversation_id=conversation_id,
        message=req.message,
        standalone_query=standalone,
        cert_ids=cert_ids,
        sources=sources,
        domain_names=domain_names,
        system=prompt.system_blocks(ctx, cert_ids),
        messages=history + [{"role": "user", "content": prompt.user_turn(req.message, sources, domain_names)}],
        rewrite_usage=rewrite_usage,
        user_id=req.user_id,
    )


# --- Steps 7-9 -----------------------------------------------------------------------------------

def _citation_payload(prep: PreparedTurn, cited: list[int]) -> list[dict]:
    out = []
    for i in cited:
        src = prep.sources[i]
        out.append(
            {
                "source_id": f"S{i + 1}",
                "chunk_id": src["id"],
                "document_title": src["document_title"],
                "domain": prep.domain_names.get(src["exam_domain_id"]),
                "source_url": (src.get("metadata") or {}).get("source_url"),
                "similarity": round(src["similarity"], 4),
                "rank": i + 1,
            }
        )
    return out


def _persist(prep: PreparedTurn, answer: str, model: str, usage: anthropic.types.Usage, citations: list[dict]) -> int:
    db = get_db()
    # Count cached prompt tokens too, so tokens_in reflects the full prompt size.
    # T4: add the rewrite call's tokens, so the assistant row records the cost of the
    # whole turn (answer + rewrite), not only the answer call.
    tokens_in = (
        usage.input_tokens
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
        + prep.rewrite_usage.input_tokens
    )
    tokens_out = usage.output_tokens + prep.rewrite_usage.output_tokens
    # One insert, so both rows share created_at; ids keep them in order.
    rows = (
        db.table("messages")
        .insert(
            [
                {"conversation_id": prep.conversation_id, "role": "user", "content": prep.message},
                {
                    "conversation_id": prep.conversation_id,
                    "role": "assistant",
                    "content": answer,
                    "model": model,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                },
            ]
        )
        .execute()
        .data
    )
    assistant_id = max(r["id"] for r in rows)
    if citations:
        db.table("message_citations").insert(
            [
                {"message_id": assistant_id, "chunk_id": c["chunk_id"], "similarity": c["similarity"], "rank": c["rank"]}
                for c in citations
            ]
        ).execute()
    return assistant_id


def stream_turn(prep: PreparedTurn) -> Iterator[tuple[str, object]]:
    """Yield ("delta", text) while Claude writes, then ("done", result_dict) after persisting."""
    s = get_settings()
    with _claude().messages.stream(
        model=s.chat_model,
        max_tokens=s.max_answer_tokens,
        system=prep.system,
        messages=prep.messages,
    ) as stream:
        for text in stream.text_stream:
            yield "delta", text
        final = stream.get_final_message()

    answer = "".join(b.text for b in final.content if b.type == "text")
    if final.stop_reason == "max_tokens":
        answer += "\n\n_(Answer cut off at the length limit.)_"

    citations = _citation_payload(prep, prompt.cited_source_indexes(answer, len(prep.sources)))
    message_id = _persist(prep, answer, final.model, final.usage, citations)
    usage = _turn_usage(prep, final.usage)
    # T4: one structured line per turn, so cost per user can be summed from the logs
    # even before a metrics system exists (L8).
    usage_log.info(
        "tutor turn user_id=%s conversation_id=%s message_id=%s model=%s rewrite_called=%s "
        "answer_in=%s answer_out=%s rewrite_in=%s rewrite_out=%s total_in=%s total_out=%s",
        prep.user_id,
        prep.conversation_id,
        message_id,
        final.model,
        prep.rewrite_usage.called,
        usage["input_tokens"],
        usage["output_tokens"],
        usage["rewrite_input_tokens"],
        usage["rewrite_output_tokens"],
        usage["total_input_tokens"],
        usage["total_output_tokens"],
    )
    yield "done", {
        "conversation_id": prep.conversation_id,
        "message_id": message_id,
        "answer": answer,
        "standalone_query": prep.standalone_query,
        "citations": citations,
        "usage": usage,
    }


def _turn_usage(prep: PreparedTurn, answer_usage: anthropic.types.Usage) -> dict:
    """Token breakdown for the `done` event (T4).

    The first three keys are unchanged from before T4, so existing clients keep
    working. The new keys add the rewrite call and the turn totals; the totals
    equal what _persist stores in messages.tokens_in / tokens_out.
    """
    cache_read = answer_usage.cache_read_input_tokens or 0
    cache_write = answer_usage.cache_creation_input_tokens or 0
    return {
        "input_tokens": answer_usage.input_tokens,
        "output_tokens": answer_usage.output_tokens,
        "cache_read_input_tokens": cache_read,
        "rewrite_input_tokens": prep.rewrite_usage.input_tokens,
        "rewrite_output_tokens": prep.rewrite_usage.output_tokens,
        "total_input_tokens": answer_usage.input_tokens + cache_read + cache_write + prep.rewrite_usage.input_tokens,
        "total_output_tokens": answer_usage.output_tokens + prep.rewrite_usage.output_tokens,
    }


def chat_turn(req: ChatRequest) -> dict:
    result: dict = {}
    for kind, payload in stream_turn(prepare_turn(req)):
        if kind == "done":
            result = payload  # type: ignore[assignment]
    return result
