"""Backfill embeddings for document_chunks. Idempotent: only (re-)embeds chunks whose
input text or embedding model changed since the last run.

    ENV_FILE=.env.test python scripts/embed_chunks.py   # local Supabase
    python scripts/embed_chunks.py                      # hosted project (.env)
    ... --force                                         # re-embed everything
"""
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.config import get_settings  # noqa: E402
from backend.app.db import get_db  # noqa: E402
from backend.app.embeddings import embed_documents  # noqa: E402


def build_input(chunk: dict, doc_title: str, domain_name: str | None) -> str:
    concept = (chunk.get("metadata") or {}).get("concept")
    header = " | ".join(p for p in (doc_title, domain_name, concept) if p)
    return f"{header}\n\n{chunk['content']}"


def main(force: bool = False) -> None:
    s = get_settings()
    db = get_db()
    print(f"Supabase: {s.supabase_url}  model: {s.embedding_provider}/{s.embedding_model} ({s.embedding_dim}d)")

    docs = {d["id"]: d["title"] for d in db.table("documents").select("id,title").execute().data}
    domains = {d["id"]: d["name"] for d in db.table("exam_domains").select("id,name").execute().data}
    chunks = (
        db.table("document_chunks")
        .select("id,document_id,exam_domain_id,content,metadata,content_hash,embedding_model")
        .order("id")
        .execute()
        .data
    )

    todo = []
    for c in chunks:
        text = build_input(c, docs.get(c["document_id"], ""), domains.get(c["exam_domain_id"]))
        h = hashlib.sha256(text.encode()).hexdigest()
        if force or c["content_hash"] != h or c["embedding_model"] != s.embedding_model:
            todo.append((c["id"], text, h))

    print(f"{len(chunks)} chunks, {len(todo)} to embed")
    if not todo:
        return

    vectors = embed_documents([t for _, t, _ in todo])
    now = datetime.now(timezone.utc).isoformat()
    for (chunk_id, _, h), vec in zip(todo, vectors):
        db.table("document_chunks").update(
            {"embedding": vec, "embedding_model": s.embedding_model, "content_hash": h, "embedded_at": now}
        ).eq("id", chunk_id).execute()
    print(f"Embedded {len(todo)} chunks.")


if __name__ == "__main__":
    main(force="--force" in sys.argv)
