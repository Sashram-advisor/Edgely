"""AI Tutor chat UI. Talks only to the FastAPI backend: no Supabase or LLM keys here.

    streamlit run ui/streamlit_app.py
    API_URL=http://localhost:8000 streamlit run ui/streamlit_app.py
"""
import json
import os
from collections.abc import Iterator

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
ALL_COURSES = None  # certification selector value meaning "search all my active courses"

st.set_page_config(page_title="AI Tutor", page_icon="🎓", layout="wide")


# --- API helpers ---------------------------------------------------------------------------------

def api_get(path: str, **params):
    r = httpx.get(f"{API_URL}{path}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=300)
def get_users() -> list[dict]:
    return api_get("/users")


def stream_chat(body: dict, result: dict) -> Iterator[str]:
    """Yield answer text from /chat/stream. Fills `result` with the meta/done/error payloads."""
    with httpx.stream("POST", f"{API_URL}/chat/stream", json=body, timeout=120) as r:
        if r.status_code != 200:
            r.read()
            result["error"] = r.json().get("detail", r.text)
            return
        event = None
        for line in r.iter_lines():
            if line.startswith("event: "):
                event = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
                if event == "delta":
                    yield data["text"]
                else:
                    result[event] = data


def citations_from_history(msg: dict) -> list[dict]:
    """Reshape nested message_citations rows from /conversations/{id}/messages to the /chat format."""
    out = []
    for c in sorted(msg.get("message_citations") or [], key=lambda c: c["rank"] or 0):
        chunk = c.get("document_chunks") or {}
        out.append(
            {
                "source_id": f"S{c['rank']}" if c["rank"] else "",
                "document_title": (chunk.get("documents") or {}).get("title", f"chunk {c['chunk_id']}"),
                "source_url": (chunk.get("metadata") or {}).get("source_url"),
                "similarity": c["similarity"],
            }
        )
    return out


def render_sources(citations: list[dict]) -> None:
    if not citations:
        return
    with st.expander(f"Sources ({len(citations)})"):
        for c in citations:
            title = f"[{c['document_title']}]({c['source_url']})" if c.get("source_url") else c["document_title"]
            sim = f" · similarity {c['similarity']:.2f}" if c.get("similarity") is not None else ""
            domain = f" · _{c['domain']}_" if c.get("domain") else ""
            st.markdown(f"**[{c['source_id']}]** {title}{domain}{sim}")


# --- Session state -------------------------------------------------------------------------------
# Streamlit reruns this whole script on every interaction; session_state is what survives a rerun.

def reset_chat() -> None:
    st.session_state.conversation_id = None
    st.session_state.conversation_cert = None
    st.session_state.messages = []


def open_conversation(conv: dict, user_id: int) -> None:
    st.session_state.conversation_id = conv["id"]
    st.session_state.conversation_cert = conv["certification_id"]
    st.session_state.messages = [
        {"role": m["role"], "content": m["content"], "citations": citations_from_history(m)}
        for m in api_get(f"/conversations/{conv['id']}/messages", user_id=user_id)
    ]


if "messages" not in st.session_state:
    reset_chat()


# --- Sidebar -------------------------------------------------------------------------------------

with st.sidebar:
    st.title("🎓 AI Tutor")
    try:
        users = get_users()
    except httpx.HTTPError as e:
        st.error(f"Can't reach the API at {API_URL}. Is uvicorn running?\n\n{e}")
        st.stop()

    st.caption("Dev only: pick a learner (no login yet)")
    user = st.selectbox("Learner", users, format_func=lambda u: f"{u['display_name']} (#{u['id']})")
    if st.session_state.get("user_id") != user["id"]:
        st.session_state.user_id = user["id"]
        reset_chat()

    ctx = api_get(f"/users/{user['id']}/context")
    st.markdown(
        f"**Level:** {ctx['experience_level'] or '-'}  \n"
        f"**Exam date:** {ctx['exam_date'] or '-'}"
    )
    weak = ctx["domain_progress"][:3]
    if weak:
        st.markdown("**Weakest domains**")
        for d in weak:
            st.progress(d["mastery_score"] / 100, text=f"{d['name']} ({d['mastery_score']:.0f}%)")

    st.divider()
    enrollments = ctx["enrollments"]
    if not enrollments:
        st.warning("No active enrollments, so the tutor has no course material to use.")
    cert_names = {e["certification_id"]: e["name"] for e in enrollments}
    if st.session_state.conversation_id:
        # An existing conversation is pinned to its scope on the backend, so don't offer a choice.
        cert_id = st.session_state.conversation_cert
        st.markdown(f"**Course:** {cert_names.get(cert_id, 'All my courses')}")
    else:
        options = [ALL_COURSES] + list(cert_names)
        default = options.index(ctx["target_certification_id"]) if ctx["target_certification_id"] in options else 0
        cert_id = st.selectbox(
            "Course",
            options,
            index=default,
            format_func=lambda c: "All my courses" if c is ALL_COURSES else cert_names[c],
        )

    if st.button("➕ New chat", use_container_width=True):
        reset_chat()
        st.rerun()

    st.subheader("Past conversations")
    for conv in api_get(f"/users/{user['id']}/conversations"):
        active = conv["id"] == st.session_state.conversation_id
        label = ("▶ " if active else "") + (conv["title"] or f"Conversation {conv['id']}")
        if st.button(label, key=f"conv-{conv['id']}", use_container_width=True):
            open_conversation(conv, user["id"])
            st.rerun()


# --- Main chat area ------------------------------------------------------------------------------

st.header(cert_names.get(cert_id, "All my courses"))

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        render_sources(m.get("citations", []))

if question := st.chat_input("Ask about your course material…"):
    st.session_state.messages.append({"role": "user", "content": question, "citations": []})
    with st.chat_message("user"):
        st.markdown(question)

    body = {"user_id": user["id"], "message": question, "conversation_id": st.session_state.conversation_id}
    if not st.session_state.conversation_id and cert_id is not ALL_COURSES:
        body["certification_id"] = cert_id

    result: dict = {}
    with st.chat_message("assistant"):
        try:
            st.write_stream(stream_chat(body, result))
        except httpx.HTTPError as e:
            result["error"] = str(e)

        if "error" in result:
            st.error(result["error"] if isinstance(result["error"], str) else result["error"].get("detail"))
            st.session_state.messages.pop()  # the backend didn't save this turn, so don't show it as sent
        else:
            done = result.get("done", {})
            render_sources(done.get("citations", []))
            st.session_state.messages.append(
                {"role": "assistant", "content": done.get("answer", ""), "citations": done.get("citations", [])}
            )
            if not st.session_state.conversation_id:
                st.session_state.conversation_id = result["meta"]["conversation_id"]
                st.session_state.conversation_cert = cert_id
                st.rerun()  # refresh the sidebar so the new conversation appears
