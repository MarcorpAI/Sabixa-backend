from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import EmployerActionType, FeedbackTesterType, UserRole, VisibilityStatus


class UserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    role: UserRole


class UserRead(UserCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class CandidateProfileCreate(BaseModel):
    user: UserCreate
    location: str = Field(min_length=2, max_length=160)
    experience: str = Field(min_length=2)
    role_interest: str = Field(min_length=2, max_length=160)


class CandidateProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    location: str
    experience: str
    role_interest: str
    visibility_status: VisibilityStatus
    created_at: datetime


class RoleTrackRead(BaseModel):
    id: str
    title: str
    role_family: str
    summary: str
    task_count: int
    benchmark: str
    competencies: list[str]


class CandidateAuthCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    location: str = Field(default="Lagos, Nigeria", min_length=2, max_length=160)
    experience: str = Field(default="Entry-level", min_length=2)
    role_track_id: str = "customer-support-associate"


class CandidateAuthRead(BaseModel):
    candidate: CandidateProfileRead
    role_track: RoleTrackRead


class EmployerProfileCreate(BaseModel):
    user: UserCreate
    company_name: str = Field(min_length=2, max_length=180)
    company_type: str = Field(min_length=2, max_length=180)
    sector: str = Field(min_length=2, max_length=120)
    support_channel: list[str] = Field(min_length=1)
    customer_volume: str = Field(min_length=2, max_length=120)


class EmployerProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_name: str
    company_type: str
    sector: str
    support_channel: list[str]
    customer_volume: str
    created_at: datetime


class IntakeAnswers(BaseModel):
    why_hiring_now: str = Field(min_length=5)
    company_stage: str = Field(min_length=2)
    channels: list[str] = Field(min_length=1)
    common_issues: str = Field(min_length=5)
    weekly_ticket_volume: str = Field(min_length=1)
    bad_hire_cost: str = Field(min_length=5)
    first_30_days: str = Field(min_length=5)
    tools_or_processes: str = Field(min_length=2)
    priority_skills: list[str] = Field(min_length=1)


class SkillMapItem(BaseModel):
    competency: str
    why_it_matters: str
    weight: int = Field(ge=0, le=100)


class TaskRubricCriterion(BaseModel):
    criterion: str
    description: str
    points: int = Field(ge=1, le=100)
    critical: bool = False


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hiring_need_id: int
    title: str
    scenario: str
    instructions: str
    output_format: str
    time_limit_minutes: int
    competencies: list[str]
    rubric: list[TaskRubricCriterion]
    created_at: datetime


class HiringNeedCreate(BaseModel):
    employer_id: int
    rough_jd: str | None = None
    intake_answers: IntakeAnswers


class HiringNeedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    rough_jd: str | None
    intake_answers: IntakeAnswers
    role_problem_summary: str
    skill_map: list[SkillMapItem]
    criteria: dict
    tasks: list[TaskRead] = []
    created_at: datetime


class SubmissionCreate(BaseModel):
    candidate_id: int
    hiring_need_id: int
    task_id: int
    answer: str = Field(min_length=2)


class EvaluationOutput(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    skill_score: int = Field(ge=0, le=100)
    evidence_score: int = Field(ge=0, le=100)
    readiness_score: int = Field(ge=0, le=100)
    role_fit_score: int = Field(ge=0, le=100)
    growth_score: int = Field(ge=0, le=100)
    confidence_band: Literal["Low", "Medium", "High"]
    confidence_reason: str
    recommended_action: Literal[
        "Interview now",
        "Give trial task",
        "Trial task",
        "Add to pool",
        "Talent pool",
        "Improve first",
        "Not enough evidence",
        "Human review required",
    ]
    rubric_breakdown: list[dict]
    evidence_quotes: list[str]
    strengths: list[str]
    gaps: list[str]
    improvement_plan: list[str]
    human_review_required: bool
    ethics_note: str


class AIEvaluationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    parsed_json: EvaluationOutput
    confidence: str
    safety_flags: list[str]
    created_at: datetime


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    hiring_need_id: int
    task_id: int
    answer: str
    evaluation: AIEvaluationRead | None = None
    created_at: datetime


class SkillPassportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: int
    submission_id: int
    public_summary: dict
    strengths: list[str]
    gaps: list[str]
    evidence_preview: str
    created_at: datetime


class SubmissionEvaluationRead(BaseModel):
    submission: SubmissionRead
    evaluation: AIEvaluationRead
    passport: SkillPassportRead
    improvement_route: dict


class ShortlistCandidate(BaseModel):
    candidate_id: int
    candidate_name: str
    submission_id: int
    passport_id: int
    overall_score: int
    task_count: int
    average_score: int
    confidence_band: str
    competency_coverage: int = Field(ge=0, le=100)
    recommended_action: str
    evidence_preview: str
    human_review_required: bool


class TrialTaskReconcileCreate(BaseModel):
    hiring_need_id: int
    trial_task_text: str = Field(min_length=10)


class TrialTaskReconcileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hiring_need_id: int
    overlap_score: int = Field(ge=0, le=100)
    repeated_competencies: list[str]
    new_competencies: list[str]
    recommendation: Literal["Keep", "Adjust", "Replace"]
    suggested_adjustment: str
    created_at: datetime


class DemoSeedRead(BaseModel):
    employer_id: int
    hiring_need_id: int
    task_ids: list[int]
    candidate_ids: list[int]
    submission_ids: list[int]
    passport_ids: list[int]
    shortlist: list[ShortlistCandidate]
    feedback_ids: list[int]


class MvpAcceptanceItem(BaseModel):
    criterion: str
    backend_support: bool
    primary_endpoint: str


class MvpStatusRead(BaseModel):
    product_statement: str
    sprint_scope: dict[str, bool | str]
    counts: dict[str, int]
    acceptance_criteria: list[MvpAcceptanceItem]
    frontend_entrypoints: list[str]


class EmployerActionCreate(BaseModel):
    employer_id: int
    candidate_id: int
    hiring_need_id: int
    action: EmployerActionType
    note: str | None = None


class EmployerActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employer_id: int
    candidate_id: int
    hiring_need_id: int
    action: EmployerActionType
    note: str | None
    created_at: datetime


class PrototypeFeedbackCreate(BaseModel):
    tester_type: FeedbackTesterType
    observations: str = Field(min_length=2)
    doubts: str = Field(min_length=2)
    trust_signals: str = Field(min_length=2)
    changes_made: str = Field(min_length=2)


class PrototypeFeedbackRead(PrototypeFeedbackCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
