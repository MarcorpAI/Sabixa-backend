from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base


class UserRole(str, enum.Enum):
    candidate = "candidate"
    employer = "employer"
    admin = "admin"


class VisibilityStatus(str, enum.Enum):
    hidden = "hidden"
    employer_visible = "employer_visible"
    needs_improvement = "needs_improvement"


class EmployerActionType(str, enum.Enum):
    shortlist = "shortlist"
    invite = "invite"
    trial_task = "trial_task"
    save = "save"
    improve_first = "improve_first"


class FeedbackTesterType(str, enum.Enum):
    candidate = "candidate"
    employer = "employer"
    recruiter = "recruiter"
    trainer = "trainer"
    admin = "admin"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)

    candidate_profile: Mapped[CandidateProfile | None] = relationship(back_populates="user")
    employer_profile: Mapped[EmployerProfile | None] = relationship(back_populates="user")


class CandidateProfile(Base, TimestampMixin):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    location: Mapped[str] = mapped_column(String(160))
    experience: Mapped[str] = mapped_column(Text)
    role_interest: Mapped[str] = mapped_column(String(160))
    visibility_status: Mapped[VisibilityStatus] = mapped_column(
        Enum(VisibilityStatus), default=VisibilityStatus.hidden
    )

    user: Mapped[User] = relationship(back_populates="candidate_profile")
    submissions: Mapped[list[Submission]] = relationship(back_populates="candidate")
    passports: Mapped[list[SkillPassport]] = relationship(back_populates="candidate")


class EmployerProfile(Base, TimestampMixin):
    __tablename__ = "employer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    company_name: Mapped[str] = mapped_column(String(180))
    company_type: Mapped[str] = mapped_column(String(180))
    sector: Mapped[str] = mapped_column(String(120))
    support_channel: Mapped[list[str]] = mapped_column(JSON)
    customer_volume: Mapped[str] = mapped_column(String(120))

    user: Mapped[User] = relationship(back_populates="employer_profile")
    hiring_needs: Mapped[list[HiringNeed]] = relationship(back_populates="employer")
    actions: Mapped[list[EmployerAction]] = relationship(back_populates="employer")


class HiringNeed(Base, TimestampMixin):
    __tablename__ = "hiring_needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"))
    rough_jd: Mapped[str | None] = mapped_column(Text, nullable=True)
    intake_answers: Mapped[dict] = mapped_column(JSON)
    role_problem_summary: Mapped[str] = mapped_column(Text)
    skill_map: Mapped[list[dict]] = mapped_column(JSON)
    criteria: Mapped[dict] = mapped_column(JSON)

    employer: Mapped[EmployerProfile] = relationship(back_populates="hiring_needs")
    tasks: Mapped[list[Task]] = relationship(back_populates="hiring_need")
    submissions: Mapped[list[Submission]] = relationship(back_populates="hiring_need")


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    hiring_need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id"))
    title: Mapped[str] = mapped_column(String(180))
    scenario: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)
    output_format: Mapped[str] = mapped_column(String(120))
    time_limit_minutes: Mapped[int] = mapped_column(Integer)
    competencies: Mapped[list[str]] = mapped_column(JSON)
    rubric: Mapped[dict] = mapped_column(JSON)

    hiring_need: Mapped[HiringNeed] = relationship(back_populates="tasks")
    submissions: Mapped[list[Submission]] = relationship(back_populates="task")


class Submission(Base, TimestampMixin):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    hiring_need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id"))
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    answer: Mapped[str] = mapped_column(Text)

    candidate: Mapped[CandidateProfile] = relationship(back_populates="submissions")
    hiring_need: Mapped[HiringNeed] = relationship(back_populates="submissions")
    task: Mapped[Task] = relationship(back_populates="submissions")
    evaluation: Mapped[AIEvaluation | None] = relationship(back_populates="submission")
    passport: Mapped[SkillPassport | None] = relationship(back_populates="submission")


class AIEvaluation(Base, TimestampMixin):
    __tablename__ = "ai_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    raw_output: Mapped[dict] = mapped_column(JSON)
    parsed_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[str] = mapped_column(String(24))
    safety_flags: Mapped[list[str]] = mapped_column(JSON)

    submission: Mapped[Submission] = relationship(back_populates="evaluation")


class SkillPassport(Base, TimestampMixin):
    __tablename__ = "skill_passports"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id"), unique=True)
    public_summary: Mapped[dict] = mapped_column(JSON)
    strengths: Mapped[list[str]] = mapped_column(JSON)
    gaps: Mapped[list[str]] = mapped_column(JSON)
    evidence_preview: Mapped[str] = mapped_column(Text)

    candidate: Mapped[CandidateProfile] = relationship(back_populates="passports")
    submission: Mapped[Submission] = relationship(back_populates="passport")


class EmployerAction(Base, TimestampMixin):
    __tablename__ = "employer_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer_profiles.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    hiring_need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id"))
    action: Mapped[EmployerActionType] = mapped_column(Enum(EmployerActionType))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    employer: Mapped[EmployerProfile] = relationship(back_populates="actions")


class PrototypeFeedback(Base, TimestampMixin):
    __tablename__ = "prototype_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    tester_type: Mapped[FeedbackTesterType] = mapped_column(Enum(FeedbackTesterType))
    observations: Mapped[str] = mapped_column(Text)
    doubts: Mapped[str] = mapped_column(Text)
    trust_signals: Mapped[str] = mapped_column(Text)
    changes_made: Mapped[str] = mapped_column(Text)


class TrialTaskReview(Base, TimestampMixin):
    __tablename__ = "trial_task_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    hiring_need_id: Mapped[int] = mapped_column(ForeignKey("hiring_needs.id"))
    trial_task_text: Mapped[str] = mapped_column(Text)
    overlap_score: Mapped[int] = mapped_column(Integer)
    repeated_competencies: Mapped[list[str]] = mapped_column(JSON)
    new_competencies: Mapped[list[str]] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(String(24))
    suggested_adjustment: Mapped[str] = mapped_column(Text)
