"""Vector search over document_chunks, scoped to the learner's certifications."""
from .config import get_settings
from .db import get_db
from .embeddings import embed_query


def retrieve(query: str, cert_ids: list[int], k: int | None = None, min_similarity: float | None = None) -> list[dict]:
    """Return up to k chunks (most similar first) from ready documents of the given certifications.

    Each row: id, document_id, document_title, exam_domain_id, content, metadata, similarity.
    """
    if not cert_ids:
        return []
    s = get_settings()
    return (
        get_db()
        .rpc(
            "match_document_chunks",
            {
                "query_embedding": embed_query(query),
                "p_certification_ids": cert_ids,
                "match_count": k or s.retrieval_k,
                "min_similarity": s.min_similarity if min_similarity is None else min_similarity,
            },
        )
        .execute()
        .data
    )
