"""Merged tutor UI for Edgely.

Two engines are available from one Streamlit app:

1. **Course tutor** - the AI_Tutor_Test implementation.  It talks to the
   untouched FastAPI app mounted at ``/ai-tutor`` and shows learner context,
   course scoping, streaming answers, citations and past conversations.
2. **Local Ollama** - the ``Ai Tutor.zip`` implementation, exposed by the
   additive bridge at ``/local-tutor``.  It answers from the bundled AWS study
   material and does not need Supabase, Claude or Gemini.

Run from the repository root:

    streamlit run ui/merged_app.py

Environment:

    API_URL=http://localhost:8000             # merged backend
    AI_TUTOR_API_URL=...                      # optional override
    LOCAL_TUTOR_API_URL=...                   # optional override
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
AI_TUTOR_URL = os.getenv("AI_TUTOR_API_URL", f"{API_URL}/ai-tutor").rstrip("/")
LOCAL_TUTOR_URL = os.getenv("LOCAL_TUTOR_API_URL", f"{API_URL}/local-tutor").rstrip("/")

ALL_COURSES = None  # certification selector value meaning "search all my active courses"

st.set_page_config(page_title="Edgely AI Tutor", page_icon="🎓", layout="wide")


# --- Shared API helpers ---------------------------------------------------------------------------


def api_get(base: str, path: str, **params: Any) -> Any:
    response = httpx.get(f"{base}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=300)
def get_users() -> list[dict]:
    return api_get(AI_TUTOR_URL, "/users")


def stream_course_chat(body: dict, result: dict) -> Iterator[str]:
    """Yield answer text from /chat/stream; fill ``result`` with event payloads."""
    with httpx.stream("POST", f"{AI_TUTOR_URL}/chat/stream", json=body, timeout=180) as response:
        if response.status_code != 200:
            response.read()
            result["error"] = response.json().get("detail", response.text)
            return

        event = None
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
                if event == "delta":
                    yield data["text"]
                else:
                    result[event] = data


def citations_from_history(message: dict) -> list[dict]:
    """Reshape nested message_citations rows into the /chat citation shape."""
    citations = []
    for citation in sorted(message.get("message_citations") or [], key=lambda item: item["rank"] or 0):
        chunk = citation.get("document_chunks") or {}
        citations.append(
            {
                "source_id": f"S{citation['rank']}" if citation["rank"] else "",
                "document_title": (chunk.get("documents") or {}).get("title", f"chunk {citation['chunk_id']}"),
                "source_url": (chunk.get("metadata") or {}).get("source_url"),
                "similarity": citation["similarity"],
            }
        )
    return citations


def render_sources(citations: list[dict]) -> None:
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)})"):
        for citation in citations:
            title = citation["document_title"]
            if citation.get("source_url"):
                title = f"[{title}]({citation['source_url']})"
            similarity = (
                f" · similarity {citation['similarity']:.2f}"
                if citation.get("similarity") is not None
                else ""
            )
            domain = f" · _{citation['domain']}_" if citation.get("domain") else ""
            st.markdown(f"**[{citation['source_id']}]** {title}{domain}{similarity}")


# --- Course tutor (AI_Tutor_Test) -----------------------------------------------------------------


def reset_course_chat() -> None:
    st.session_state.course_conversation_id = None
    st.session_state.course_conversation_cert = None
    st.session_state.course_messages = []


def open_course_conversation(conversation: dict, user_id: int) -> None:
    st.session_state.course_conversation_id = conversation["id"]
    st.session_state.course_conversation_cert = conversation["certification_id"]
    st.session_state.course_messages = [
        {
            "role": message["role"],
            "content": message["content"],
            "citations": citations_from_history(message),
        }
        for message in api_get(
            AI_TUTOR_URL,
            f"/conversations/{conversation['id']}/messages",
            user_id=user_id,
        )
    ]


def render_course_tutor() -> None:
    if "course_messages" not in st.session_state:
        reset_course_chat()

    with st.sidebar:
        st.header("Course tutor")
        try:
            users = get_users()
        except httpx.HTTPError as exc:
            st.error(f"Can't reach the merged API at {AI_TUTOR_URL}.\n\n{exc}")
            st.stop()

        if not users:
            st.warning("No learners are available in the database.")
            st.stop()

        st.caption("Dev only: pick a learner (no login yet)")
        user = st.selectbox(
            "Learner",
            users,
            format_func=lambda item: f"{item['display_name']} (#{item['id']})",
            key="course_user",
        )
        if st.session_state.get("course_user_id") != user["id"]:
            st.session_state.course_user_id = user["id"]
            reset_course_chat()

        context = api_get(AI_TUTOR_URL, f"/users/{user['id']}/context")
        st.markdown(
            f"**Level:** {context['experience_level'] or '-'}  \n"
            f"**Exam date:** {context['exam_date'] or '-'}"
        )
        weak_domains = context["domain_progress"][:3]
        if weak_domains:
            st.markdown("**Weakest domains**")
            for domain in weak_domains:
                st.progress(
                    domain["mastery_score"] / 100,
                    text=f"{domain['name']} ({domain['mastery_score']:.0f}%)",
                )

        st.divider()
        enrollments = context["enrollments"]
        cert_names = {enrollment["certification_id"]: enrollment["name"] for enrollment in enrollments}
        if not enrollments:
            st.warning("No active enrollments, so the tutor has no course material to use.")
            cert_id = None
        elif st.session_state.course_conversation_id:
            # An existing conversation is pinned to its scope by the backend.
            cert_id = st.session_state.course_conversation_cert
            st.markdown(f"**Course:** {cert_names.get(cert_id, 'All my courses')}")
        else:
            options = [ALL_COURSES] + list(cert_names)
            default = (
                options.index(context["target_certification_id"])
                if context["target_certification_id"] in options
                else 0
            )
            cert_id = st.selectbox(
                "Course",
                options,
                index=default,
                format_func=lambda value: "All my courses" if value is ALL_COURSES else cert_names[value],
                key="course_cert",
            )

        if st.button("➕ New chat", use_container_width=True, key="course_new"):
            reset_course_chat()
            st.rerun()

        st.subheader("Past conversations")
        for conversation in api_get(AI_TUTOR_URL, f"/users/{user['id']}/conversations"):
            active = conversation["id"] == st.session_state.course_conversation_id
            label = ("▶ " if active else "") + (conversation["title"] or f"Conversation {conversation['id']}")
            if st.button(label, key=f"course-conv-{conversation['id']}", use_container_width=True):
                open_course_conversation(conversation, user["id"])
                st.rerun()

    st.header(cert_names.get(cert_id, "All my courses"))

    for message in st.session_state.course_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_sources(message.get("citations", []))

    question = st.chat_input(
        "Ask about your course material…",
        disabled=not enrollments,
    )
    if not question:
        return

    st.session_state.course_messages.append({"role": "user", "content": question, "citations": []})
    with st.chat_message("user"):
        st.markdown(question)

    body = {
        "user_id": user["id"],
        "message": question,
        "conversation_id": st.session_state.course_conversation_id,
    }
    if not st.session_state.course_conversation_id and cert_id is not ALL_COURSES:
        body["certification_id"] = cert_id

    result: dict = {}
    with st.chat_message("assistant"):
        try:
            st.write_stream(stream_course_chat(body, result))
        except httpx.HTTPError as exc:
            result["error"] = str(exc)

        if "error" in result:
            detail = result["error"] if isinstance(result["error"], str) else result["error"].get("detail")
            st.error(detail)
            st.session_state.course_messages.pop()
            return

        done = result.get("done", {})
        render_sources(done.get("citations", []))
        st.session_state.course_messages.append(
            {
                "role": "assistant",
                "content": done.get("answer", ""),
                "citations": done.get("citations", []),
            }
        )
        if not st.session_state.course_conversation_id:
            st.session_state.course_conversation_id = result["meta"]["conversation_id"]
            st.session_state.course_conversation_cert = cert_id
            st.rerun()


# --- Local Ollama tutor (Ai Tutor.zip) ------------------------------------------------------------


@st.cache_data(ttl=30)
def get_local_health() -> dict:
    return api_get(LOCAL_TUTOR_URL, "/health")


def render_local_tutor() -> None:
    if "local_messages" not in st.session_state:
        st.session_state.local_messages = []

    with st.sidebar:
        st.header("Local Ollama tutor")
        try:
            health = get_local_health()
        except httpx.HTTPError as exc:
            st.error(f"Can't reach the local tutor bridge at {LOCAL_TUTOR_URL}.\n\n{exc}")
            st.stop()

        st.caption("Offline AWS Cloud Practitioner tutor")
        st.markdown(
            f"**Material:** `{health['material']}`  \n"
            f"**Sections:** {health['sections']}  \n"
            f"**Embed model:** `{health['embed_model']}`  \n"
            f"**Chat model:** `{health['chat_model']}`"
        )
        if not health["ollama_reachable"]:
            st.warning(
                "Ollama is not reachable. Start it with `ollama serve`, then pull "
                f"`{health['embed_model']}` and `{health['chat_model']}`."
            )

        if st.button("🧹 Clear chat", use_container_width=True, key="local_clear"):
            st.session_state.local_messages = []
            st.rerun()

    st.header("Local AWS Cloud Practitioner Tutor")
    st.caption(
        "Powered by Ollama + the bundled study material. This mode does not use Supabase, "
        "Claude or Gemini."
    )

    for message in st.session_state.local_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            render_sources(message.get("citations", []))

    question = st.chat_input("Ask about AWS…", key="local_question")
    if not question:
        return

    st.session_state.local_messages.append({"role": "user", "content": question, "citations": []})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Searching the study material…"):
                response = httpx.post(
                    f"{LOCAL_TUTOR_URL}/chat",
                    json={"message": question, "max_sections": 2},
                    timeout=180,
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            detail = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                try:
                    detail = exc.response.json().get("detail", detail)
                except ValueError:
                    detail = exc.response.text
            st.error(detail)
            st.session_state.local_messages.pop()
            return

        st.markdown(payload["answer"])
        citations = [
            {
                "source_id": source["source_id"],
                "document_title": source["title"],
                "similarity": source["similarity"],
            }
            for source in payload.get("sources", [])
        ]
        render_sources(citations)
        st.session_state.local_messages.append(
            {"role": "assistant", "content": payload["answer"], "citations": citations}
        )


# --- Entry point ----------------------------------------------------------------------------------

st.sidebar.title("🎓 Edgely AI Tutor")
mode = st.sidebar.radio(
    "Tutor engine",
    ["Course tutor (Edgely RAG)", "Local Ollama (offline)"],
    key="tutor_mode",
)
st.sidebar.divider()

if mode == "Course tutor (Edgely RAG)":
    render_course_tutor()
else:
    render_local_tutor()
