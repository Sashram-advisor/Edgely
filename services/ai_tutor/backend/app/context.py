"""Learner context: who the user is, what they're enrolled in, and where they're weak."""
from dataclasses import dataclass, field

from .db import get_db


class UserNotFound(Exception):
    pass


@dataclass
class LearnerContext:
    user_id: int
    display_name: str
    experience_level: str | None = None
    exam_date: str | None = None
    target_certification_id: int | None = None
    goals: dict = field(default_factory=dict)
    enrollments: list[dict] = field(default_factory=list)  # active only: certification_id, name, goal, deadline
    domain_progress: list[dict] = field(default_factory=list)  # weakest first: name, certification_id, mastery_score

    @property
    def active_cert_ids(self) -> list[int]:
        return [e["certification_id"] for e in self.enrollments]

    def cert_name(self, cert_id: int) -> str | None:
        return next((e["name"] for e in self.enrollments if e["certification_id"] == cert_id), None)

    def weak_domains(self, cert_ids: list[int], n: int = 3) -> list[dict]:
        return [d for d in self.domain_progress if d["certification_id"] in cert_ids][:n]


def load_learner_context(user_id: int) -> LearnerContext:
    db = get_db()

    users = db.table("users").select("id,display_name").eq("id", user_id).execute().data
    if not users:
        raise UserNotFound(user_id)

    profile = next(iter(db.table("learner_profiles").select("*").eq("user_id", user_id).execute().data), {})

    enrollments = (
        db.table("enrollments")
        .select("certification_id,goal,deadline,certifications(name)")
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
        .data
    )

    # progress -> exam_domains has two identical FKs (_fkey and _fkey1), so PostgREST needs the hint.
    progress = (
        db.table("progress")
        .select("mastery_score,exam_domains!progress_exam_domain_id_fkey(name,certification_id)")
        .eq("user_id", user_id)
        .order("mastery_score")
        .execute()
        .data
    )

    return LearnerContext(
        user_id=user_id,
        display_name=users[0]["display_name"],
        experience_level=profile.get("experience_level"),
        exam_date=profile.get("exam_date"),
        target_certification_id=profile.get("target_certification_id"),
        goals=profile.get("goals") or {},
        enrollments=[
            {
                "certification_id": e["certification_id"],
                "name": e["certifications"]["name"],
                "goal": e["goal"],
                "deadline": e["deadline"],
            }
            for e in enrollments
        ],
        domain_progress=[
            {
                "name": p["exam_domains"]["name"],
                "certification_id": p["exam_domains"]["certification_id"],
                "mastery_score": float(p["mastery_score"]),
            }
            for p in progress
        ],
    )
