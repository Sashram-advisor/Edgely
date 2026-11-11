"""Prompt building. Pure functions: no DB or API calls, so they're easy to test and tweak."""
import json
import re
from html import escape

from .context import LearnerContext

# Static and identical on every request, so it's the cacheable prefix. Keep anything per-user out of it.
TUTOR_INSTRUCTIONS = """\
You are an AI tutor helping a learner prepare for an IT certification exam.

How to answer:
- Answer only from the <source> blocks in the learner's latest message. Do not use outside knowledge to fill gaps.
- Cite every claim that comes from a source with its id in square brackets, e.g. [S1] or [S2][S3]. Never invent ids.
- If the sources don't cover the question, say plainly that it isn't covered in their course material, and suggest \
what they could ask instead. Do not cite anything in that case.
- Match depth to the learner's experience level: define terms for beginners, skip basics for advanced learners.
- When a source belongs to an exam domain, mention the domain so the learner knows where it fits in the exam.
- If the question touches one of the learner's weak domains, point that out briefly and encourage practice.
- Be concise: short paragraphs or bullet points, no filler."""

REWRITE_INSTRUCTIONS = """\
Rewrite the learner's latest message as a standalone question that can be understood without the conversation. \
Resolve pronouns and references like "it", "that one" or "what about X" using the conversation. \
If it is already standalone, return it unchanged. Output only the question, nothing else."""

_CITATION_RE = re.compile(r"\[S(\d+)\]")


def learner_block(ctx: LearnerContext, cert_ids: list[int]) -> str:
    certs = ", ".join(ctx.cert_name(c) or str(c) for c in cert_ids)
    weak = ", ".join(f"{d['name']} ({d['mastery_score']:.0f}%)" for d in ctx.weak_domains(cert_ids)) or "none recorded"
    lines = [
        "<learner>",
        f"Name: {ctx.display_name}",
        f"Certification(s) in scope: {certs}",
        f"Experience level: {ctx.experience_level or 'unknown'}",
        f"Exam date: {ctx.exam_date or 'not set'}",
        f"Goals: {json.dumps(ctx.goals, sort_keys=True) if ctx.goals else 'not set'}",
        f"Lowest-mastery exam domains, weakest first: {weak}",
        "</learner>",
    ]
    return "\n".join(lines)


def system_blocks(ctx: LearnerContext, cert_ids: list[int]) -> list[dict]:
    # The cache breakpoint goes on the static block; the learner block after it changes per user.
    return [
        {"type": "text", "text": TUTOR_INSTRUCTIONS, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": learner_block(ctx, cert_ids)},
    ]


def format_sources(sources: list[dict], domain_names: dict[int, str]) -> str:
    if not sources:
        return "<sources>No matching course material was found.</sources>"
    parts = []
    for i, s in enumerate(sources, 1):
        attrs = {
            "id": f"S{i}",
            "title": s["document_title"],
            "domain": domain_names.get(s["exam_domain_id"], ""),
            "url": (s.get("metadata") or {}).get("source_url", ""),
        }
        attr_str = " ".join(f'{k}="{escape(str(v))}"' for k, v in attrs.items() if v)
        parts.append(f"<source {attr_str}>\n{s['content']}\n</source>")
    return "<sources>\n" + "\n".join(parts) + "\n</sources>"


def user_turn(question: str, sources: list[dict], domain_names: dict[int, str]) -> str:
    return f"{format_sources(sources, domain_names)}\n\n{question}"


def cited_source_indexes(answer: str, n_sources: int) -> list[int]:
    """0-based indexes of sources cited as [S#] in the answer, in first-cited order, ignoring invented ids."""
    seen: list[int] = []
    for m in _CITATION_RE.finditer(answer):
        i = int(m.group(1)) - 1
        if 0 <= i < n_sources and i not in seen:
            seen.append(i)
    return seen
