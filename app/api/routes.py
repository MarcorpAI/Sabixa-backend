from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_session
from app.models import (
    AIEvaluation,
    CandidateProfile,
    EmployerAction,
    EmployerProfile,
    FeedbackTesterType,
    PrototypeFeedback,
    SkillPassport,
    Submission,
    Task,
    TrialTaskReview,
    User,
    UserRole,
    VisibilityStatus,
)
from app.models.entities import HiringNeed
from app.schemas import (
    CandidateAuthCreate,
    CandidateAuthRead,
    CandidateProfileCreate,
    CandidateProfileRead,
    DemoSeedRead,
    EmployerActionCreate,
    EmployerActionRead,
    EmployerProfileCreate,
    EmployerProfileRead,
    HiringNeedCreate,
    HiringNeedRead,
    IntakeAnswers,
    MvpStatusRead,
    PrototypeFeedbackCreate,
    PrototypeFeedbackRead,
    ShortlistCandidate,
    SkillPassportRead,
    SubmissionCreate,
    SubmissionEvaluationRead,
    SubmissionRead,
    TaskRead,
    TrialTaskReconcileCreate,
    TrialTaskReconcileRead,
)
from app.services import (
    build_criteria,
    build_improvement_route,
    build_passport_summary,
    build_role_problem_summary,
    build_skill_map,
    default_task_pack,
    evaluate_work_sample,
    reconcile_trial_task,
    role_tracks,
    task_count_readiness,
)
from app.services.ai import (
    evaluate_with_ai,
    generate_skill_map,
    generate_tasks,
    summarize_passport,
)

router = APIRouter()

settings = get_settings()

@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "sabixa-api"}


@router.get("/role-tracks")
async def list_role_tracks() -> list:
    return role_tracks()


@router.post("/auth/candidate", response_model=CandidateAuthRead, status_code=status.HTTP_201_CREATED)
async def candidate_auth(payload: CandidateAuthCreate, session: Session = Depends(get_session)) -> dict:
    track = _role_track_or_404(payload.role_track_id)
    existing_user = session.scalar(select(User).where(User.email == payload.email, User.role == UserRole.candidate))
    if existing_user and existing_user.candidate_profile:
        return {"candidate": existing_user.candidate_profile, "role_track": track}

    user = existing_user or User(full_name=payload.full_name, email=payload.email, role=UserRole.candidate)
    user.full_name = payload.full_name
    profile = CandidateProfile(
        user=user,
        location=payload.location,
        experience=payload.experience,
        role_interest=track.title,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return {"candidate": profile, "role_track": track}


@router.post("/auth/employer", response_model=EmployerProfileRead, status_code=status.HTTP_201_CREATED)
async def employer_auth(payload: EmployerProfileCreate, session: Session = Depends(get_session)) -> EmployerProfile:
    existing_user = session.scalar(select(User).where(User.email == payload.user.email, User.role == UserRole.employer))
    if existing_user and existing_user.employer_profile:
        return existing_user.employer_profile
    return await create_employer_profile(payload, session)


@router.get("/mvp/status", response_model=MvpStatusRead)
async def mvp_status(session: Session = Depends(get_session)) -> dict:
    counts = {
        "users": _count_rows(session, User),
        "candidate_profiles": _count_rows(session, CandidateProfile),
        "employer_profiles": _count_rows(session, EmployerProfile),
        "hiring_needs": _count_rows(session, HiringNeed),
        "tasks": _count_rows(session, Task),
        "submissions": _count_rows(session, Submission),
        "evaluations": _count_rows(session, AIEvaluation),
        "skill_passports": _count_rows(session, SkillPassport),
        "employer_actions": _count_rows(session, EmployerAction),
        "prototype_feedback": _count_rows(session, PrototypeFeedback),
        "trial_task_reviews": _count_rows(session, TrialTaskReview),
    }
    ai_status = "configured" if settings.groq_api_key else "fallback_only"
    return {
        "product_statement": (
            "Sabixa turns customer support hiring needs into skill maps, real work samples, "
            "structured evidence, ranked shortlists, and candidate improvement routes."
        ),
        "sprint_scope": {
            "employer_hiring_need_intake": True,
            "ai_skill_map_and_3_task_pack": True,
            "candidate_task_submission": True,
            "ai_scoring_with_fallback": True,
            "skill_passport": True,
            "employer_ranked_shortlist": True,
            "improvement_route": True,
            "trial_task_reconciliation": True,
            "simple_prototype_auth": True,
            "role_track_onboarding": True,
            "prototype_feedback": True,
            "ai_provider": ai_status,
        },
        "counts": counts,
        "acceptance_criteria": [
            {
                "criterion": "Employer can create a hiring need from intake questions.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/hiring-needs",
            },
            {
                "criterion": "System shows a generated customer-support skill map.",
                "backend_support": True,
                "primary_endpoint": "GET /api/v1/hiring-needs/{hiring_need_id}",
            },
            {
                "criterion": "System shows a recommended 3-task assessment pack.",
                "backend_support": True,
                "primary_endpoint": "GET /api/v1/hiring-needs/{hiring_need_id}/tasks",
            },
            {
                "criterion": "Candidate can complete at least one task.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/submissions",
            },
            {
                "criterion": "AI or fallback evaluator produces structured scoring and feedback.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/submissions",
            },
            {
                "criterion": "Candidate sees a skill passport.",
                "backend_support": True,
                "primary_endpoint": "GET /api/v1/skill-passports/{passport_id}",
            },
            {
                "criterion": "Employer sees ranked candidates and opens evidence detail.",
                "backend_support": True,
                "primary_endpoint": "GET /api/v1/hiring-needs/{hiring_need_id}/shortlist",
            },
            {
                "criterion": "Employer trial task overlap report appears.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/trial-task-reconcile",
            },
            {
                "criterion": "Below-benchmark candidate sees improvement route.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/submissions",
            },
            {
                "criterion": "Ethics note and human review reminder are visible.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/submissions",
            },
            {
                "criterion": "Team can show what changed after at least 3 user tests.",
                "backend_support": True,
                "primary_endpoint": "POST /api/v1/prototype-feedback",
            },
        ],
        "frontend_entrypoints": [
            "/",
            "/candidate/onboarding",
            "/candidate/assessment",
            "/employer/intake",
            "/employer/hiring-needs/{hiring_need_id}",
            "/candidate/tasks/{task_id}",
            "/candidate/passports/{passport_id}",
            "/employer/hiring-needs/{hiring_need_id}/shortlist",
            "/feedback",
        ],
    }


@router.post("/demo/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_demo(session: Session = Depends(get_session)) -> None:
    _clear_demo_data(session)
    session.commit()


@router.post("/demo/seed", response_model=DemoSeedRead, status_code=status.HTTP_201_CREATED)
async def seed_demo(session: Session = Depends(get_session)) -> DemoSeedRead:
    _clear_demo_data(session)
    employer = _create_demo_employer(session)
    candidates = _create_demo_candidates(session)
    session.flush()

    answers = _demo_intake_answers()
    skill_map = build_skill_map(answers)
    need = HiringNeed(
        employer_id=employer.id,
        rough_jd="Customer support assistant for WhatsApp complaints, refunds, and ticket summaries.",
        intake_answers=answers.model_dump(),
        role_problem_summary=build_role_problem_summary(answers, "Customer support assistant for WhatsApp complaints."),
        skill_map=[item.model_dump() for item in skill_map],
        criteria=build_criteria(answers),
    )
    session.add(need)
    session.flush()

    tasks = []
    for task_data in default_task_pack(answers):
        task = Task(hiring_need_id=need.id, **task_data)
        session.add(task)
        tasks.append(task)
    session.flush()

    submissions = [
        _create_submission_bundle(
            session,
            candidate=candidates[0],
            hiring_need=need,
            task=tasks[0],
            answer=(
                "Hi Sarah, I am sorry your order has taken this long. I understand how frustrating "
                "it is after paying five days ago. I will check the delivery status with dispatch "
                "now and update you before 4pm today. If it cannot move today, I will escalate it "
                "to operations for the refund option under our policy."
            ),
        ),
        _create_submission_bundle(
            session,
            candidate=candidates[1],
            hiring_need=need,
            task=tasks[1],
            answer=(
                "I understand why you are upset and I am sorry this refund has become stressful. "
                "I will review the order against our refund policy now, escalate the case to my "
                "supervisor, and update you today with the approved next step."
            ),
        ),
        _create_submission_bundle(
            session,
            candidate=candidates[2],
            hiring_need=need,
            task=tasks[0],
            answer="We will check.",
        ),
    ]

    feedback_rows = [
        PrototypeFeedback(
            tester_type=FeedbackTesterType.candidate,
            observations="The passport makes the score understandable.",
            doubts="Candidate wanted clearer retry timing.",
            trust_signals="Strengths and gaps were visible.",
            changes_made="Added a retry route and practice focus.",
        ),
        PrototypeFeedback(
            tester_type=FeedbackTesterType.employer,
            observations="Shortlist evidence made comparison faster.",
            doubts="Employer asked how low confidence is handled.",
            trust_signals="Human review reminder increased trust.",
            changes_made="Added confidence band and review requirement.",
        ),
        PrototypeFeedback(
            tester_type=FeedbackTesterType.trainer,
            observations="Gaps can guide cohort coaching.",
            doubts="Trainer asked for task-level rubric visibility.",
            trust_signals="Rubric criteria are attached to each task.",
            changes_made="Exposed rubric in task pack response.",
        ),
    ]
    session.add_all(feedback_rows)
    session.commit()

    shortlist = _build_shortlist(session, need.id)
    return DemoSeedRead(
        employer_id=employer.id,
        hiring_need_id=need.id,
        task_ids=[task.id for task in tasks],
        candidate_ids=[candidate.id for candidate in candidates],
        submission_ids=[submission.id for submission in submissions],
        passport_ids=[submission.passport.id for submission in submissions if submission.passport is not None],
        shortlist=shortlist,
        feedback_ids=[feedback.id for feedback in feedback_rows],
    )


@router.post("/candidate-profiles", response_model=CandidateProfileRead, status_code=status.HTTP_201_CREATED)
async def create_candidate_profile(
    payload: CandidateProfileCreate, session: Session = Depends(get_session)
) -> CandidateProfile:
    user = User(**payload.user.model_dump())
    profile = CandidateProfile(
        user=user,
        location=payload.location,
        experience=payload.experience,
        role_interest=payload.role_interest,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.post("/employer-profiles", response_model=EmployerProfileRead, status_code=status.HTTP_201_CREATED)
async def create_employer_profile(
    payload: EmployerProfileCreate, session: Session = Depends(get_session)
) -> EmployerProfile:
    user = User(**payload.user.model_dump())
    profile = EmployerProfile(
        user=user,
        company_name=payload.company_name,
        company_type=payload.company_type,
        sector=payload.sector,
        support_channel=payload.support_channel,
        customer_volume=payload.customer_volume,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.post("/hiring-needs", response_model=HiringNeedRead, status_code=status.HTTP_201_CREATED)
async def create_hiring_need(payload: HiringNeedCreate, session: Session = Depends(get_session)) -> HiringNeed:
    employer = session.get(EmployerProfile, payload.employer_id)
    if employer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer profile not found")

    ai_skill_map = await generate_skill_map(payload.intake_answers)
    if ai_skill_map and len(ai_skill_map) > 0:
        skill_map = ai_skill_map
    else:
        skill_map = build_skill_map(payload.intake_answers)

    need = HiringNeed(
        employer_id=payload.employer_id,
        rough_jd=payload.rough_jd,
        intake_answers=payload.intake_answers.model_dump(),
        role_problem_summary=build_role_problem_summary(payload.intake_answers, payload.rough_jd),
        skill_map=[item.model_dump() for item in skill_map],
        criteria=build_criteria(payload.intake_answers),
    )
    session.add(need)
    session.flush()

    ai_tasks = await generate_tasks(payload.intake_answers, skill_map)
    if ai_tasks and len(ai_tasks) == 3:
        tasks_to_use = ai_tasks
    else:
        tasks_to_use = default_task_pack(payload.intake_answers)

    for task_data in tasks_to_use:
        session.add(Task(hiring_need_id=need.id, **task_data))

    session.commit()
    return _get_hiring_need_or_404(session, need.id)


@router.get("/hiring-needs/{hiring_need_id}", response_model=HiringNeedRead)
async def get_hiring_need(hiring_need_id: int, session: Session = Depends(get_session)) -> HiringNeed:
    return _get_hiring_need_or_404(session, hiring_need_id)


@router.get("/hiring-needs/{hiring_need_id}/tasks", response_model=list[TaskRead])
async def list_tasks(hiring_need_id: int, session: Session = Depends(get_session)) -> list[Task]:
    _get_hiring_need_or_404(session, hiring_need_id)
    result = session.execute(select(Task).where(Task.hiring_need_id == hiring_need_id).order_by(Task.id))
    return list(result.scalars().all())


@router.post("/submissions", response_model=SubmissionEvaluationRead, status_code=status.HTTP_201_CREATED)
async def create_submission(payload: SubmissionCreate, session: Session = Depends(get_session)) -> dict:
    candidate = session.get(CandidateProfile, payload.candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate profile not found")

    need = _get_hiring_need_or_404(session, payload.hiring_need_id)
    task = session.get(Task, payload.task_id)
    if task is None or task.hiring_need_id != need.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found for this hiring need")

    submission = Submission(
        candidate_id=payload.candidate_id,
        hiring_need_id=payload.hiring_need_id,
        task_id=payload.task_id,
        answer=payload.answer,
    )
    session.add(submission)
    session.flush()

    task_dict = {
        "title": task.title,
        "scenario": task.scenario,
        "instructions": task.instructions,
        "output_format": task.output_format,
        "rubric": task.rubric,
    }
    priority_skills = need.criteria.get("priority_skills", [])

    ai_evaluation = await evaluate_with_ai(payload.answer, task_dict, priority_skills)

    if ai_evaluation:
        evaluation_output = ai_evaluation
    else:
        evaluation_output = evaluate_work_sample(
            answer=payload.answer,
            task_competencies=task.competencies,
            priority_skills=priority_skills,
        )

    evaluation = AIEvaluation(
        submission_id=submission.id,
        raw_output=evaluation_output.model_dump(),
        parsed_json=evaluation_output.model_dump(),
        confidence=evaluation_output.confidence_band,
        safety_flags=[] if not evaluation_output.human_review_required else ["human_review_required"],
    )
    session.add(evaluation)

    passport_summary = await summarize_passport(evaluation_output, payload.answer) if ai_evaluation else build_passport_summary(evaluation_output, payload.answer)

    passport = SkillPassport(
        candidate_id=payload.candidate_id,
        submission_id=submission.id,
        public_summary=passport_summary,
        strengths=evaluation_output.strengths,
        gaps=evaluation_output.gaps,
        evidence_preview=payload.answer[:280],
    )
    session.add(passport)

    candidate.visibility_status = (
        VisibilityStatus.employer_visible
        if evaluation_output.overall_score >= 70 and not evaluation_output.human_review_required
        else VisibilityStatus.needs_improvement
    )

    session.commit()
    submission = _get_submission_or_404(session, submission.id)
    evaluation = submission.evaluation
    if evaluation is None or submission.passport is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Evaluation was not created")

    return {
        "submission": submission,
        "evaluation": evaluation,
        "passport": submission.passport,
        "improvement_route": build_improvement_route(evaluation_output),
    }


@router.post("/trial-task-reconcile", response_model=TrialTaskReconcileRead, status_code=status.HTTP_201_CREATED)
async def trial_task_reconcile(
    payload: TrialTaskReconcileCreate, session: Session = Depends(get_session)
) -> TrialTaskReview:
    need = _get_hiring_need_or_404(session, payload.hiring_need_id)
    assessment_tasks = [
        {"title": task.title, "scenario": task.scenario, "competencies": task.competencies} for task in need.tasks
    ]
    result = reconcile_trial_task(payload.trial_task_text, assessment_tasks)
    review = TrialTaskReview(hiring_need_id=need.id, trial_task_text=payload.trial_task_text, **result)
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
async def get_submission(submission_id: int, session: Session = Depends(get_session)) -> Submission:
    return _get_submission_or_404(session, submission_id)


@router.get("/skill-passports/{passport_id}", response_model=SkillPassportRead)
async def get_skill_passport(passport_id: int, session: Session = Depends(get_session)) -> SkillPassport:
    passport = session.get(SkillPassport, passport_id)
    if passport is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill passport not found")
    return passport


@router.get("/hiring-needs/{hiring_need_id}/shortlist", response_model=list[ShortlistCandidate])
async def get_shortlist(hiring_need_id: int, session: Session = Depends(get_session)) -> list[ShortlistCandidate]:
    _get_hiring_need_or_404(session, hiring_need_id)
    return _build_shortlist(session, hiring_need_id)


@router.post("/employer-actions", response_model=EmployerActionRead, status_code=status.HTTP_201_CREATED)
async def create_employer_action(
    payload: EmployerActionCreate, session: Session = Depends(get_session)
) -> EmployerAction:
    action = EmployerAction(**payload.model_dump())
    session.add(action)
    session.commit()
    session.refresh(action)
    return action


@router.post("/prototype-feedback", response_model=PrototypeFeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_prototype_feedback(
    payload: PrototypeFeedbackCreate, session: Session = Depends(get_session)
) -> PrototypeFeedback:
    feedback = PrototypeFeedback(**payload.model_dump())
    session.add(feedback)
    session.commit()
    session.refresh(feedback)
    return feedback


@router.get("/prototype-feedback", response_model=list[PrototypeFeedbackRead])
async def list_prototype_feedback(session: Session = Depends(get_session)) -> list[PrototypeFeedback]:
    result = session.execute(select(PrototypeFeedback).order_by(PrototypeFeedback.created_at))
    return list(result.scalars().all())


def _build_shortlist(session: Session, hiring_need_id: int) -> list[ShortlistCandidate]:
    result = session.execute(
        select(Submission)
        .where(Submission.hiring_need_id == hiring_need_id)
        .options(
            selectinload(Submission.evaluation),
            selectinload(Submission.passport),
            selectinload(Submission.candidate).selectinload(CandidateProfile.user),
            selectinload(Submission.task),
        )
    )
    submissions = [submission for submission in result.scalars().all() if submission.evaluation and submission.passport]
    grouped: dict[int, list[Submission]] = {}
    for submission in submissions:
        grouped.setdefault(submission.candidate_id, []).append(submission)

    rows = []
    for candidate_submissions in grouped.values():
        latest = sorted(candidate_submissions, key=lambda item: item.created_at)[-1]
        if latest.evaluation is None or latest.passport is None:
            continue
        parsed = latest.evaluation.parsed_json
        scores = [item.evaluation.parsed_json["overall_score"] for item in candidate_submissions if item.evaluation]
        readiness = task_count_readiness(
            scores,
            has_critical_low=any(
                any(row.get("critical") and row.get("score", 100) < 60 for row in item.evaluation.parsed_json.get("rubric_breakdown", []))
                for item in candidate_submissions
                if item.evaluation
            ),
            has_low_confidence=any(
                item.evaluation.parsed_json.get("human_review_required", False) for item in candidate_submissions if item.evaluation
            ),
        )
        covered = _competency_coverage(latest.task.competencies, parsed)
        rows.append(
            ShortlistCandidate(
                candidate_id=latest.candidate_id,
                candidate_name=latest.candidate.user.full_name,
                submission_id=latest.id,
                passport_id=latest.passport.id,
                overall_score=readiness["average_score"],
                task_count=readiness["task_count"],
                average_score=readiness["average_score"],
                confidence_band=parsed["confidence_band"],
                competency_coverage=covered,
                recommended_action=readiness["recommended_action"],
                evidence_preview=latest.passport.evidence_preview,
                human_review_required=parsed.get("human_review_required", parsed["confidence_band"] == "Low"),
            )
        )
    return sorted(rows, key=lambda item: (item.overall_score, item.competency_coverage), reverse=True)


def _clear_demo_data(session: Session) -> None:
    for model in (
        PrototypeFeedback,
        EmployerAction,
        SkillPassport,
        AIEvaluation,
        Submission,
        TrialTaskReview,
        Task,
        HiringNeed,
        CandidateProfile,
        EmployerProfile,
        User,
    ):
        session.execute(delete(model))


def _create_demo_employer(session: Session) -> EmployerProfile:
    employer = EmployerProfile(
        user=User(full_name="Ada Employer", email="ada.employer@sabixa.demo", role=UserRole.employer),
        company_name="Lagos Style Market",
        company_type="Growing ecommerce SME",
        sector="Retail ecommerce",
        support_channel=["WhatsApp", "Email"],
        customer_volume="250 to 400 messages weekly",
    )
    session.add(employer)
    return employer


def _create_demo_candidates(session: Session) -> list[CandidateProfile]:
    candidates = [
        CandidateProfile(
            user=User(full_name="Amaka Okafor", email="amaka@sabixa.demo", role=UserRole.candidate),
            location="Lagos, Nigeria",
            experience="Six months handling Instagram and WhatsApp customer messages.",
            role_interest="Entry-level customer support",
        ),
        CandidateProfile(
            user=User(full_name="Tunde Bello", email="tunde@sabixa.demo", role=UserRole.candidate),
            location="Ibadan, Nigeria",
            experience="One year as a retail floor assistant resolving customer complaints.",
            role_interest="Customer operations assistant",
        ),
        CandidateProfile(
            user=User(full_name="Blessing Nnaji", email="blessing@sabixa.demo", role=UserRole.candidate),
            location="Enugu, Nigeria",
            experience="Completed customer service training but has limited live support experience.",
            role_interest="Entry-level customer support",
        ),
    ]
    session.add_all(candidates)
    return candidates


def _demo_intake_answers() -> IntakeAnswers:
    return IntakeAnswers(
        why_hiring_now="delayed deliveries are increasing and support messages are piling up",
        company_stage="Growing fashion ecommerce SME in Lagos",
        channels=["WhatsApp", "Email"],
        common_issues="delayed delivery, refund pressure, wrong size, missing order updates",
        weekly_ticket_volume="250 to 400 messages weekly",
        bad_hire_cost="refund losses, angry reviews, and poor operations handoff",
        first_30_days="reply to WhatsApp complaints and escalate urgent refund cases",
        tools_or_processes="Google Sheets, WhatsApp Business, refund policy checklist",
        priority_skills=["Empathy", "Clarity", "Escalation judgement", "Ownership"],
    )


def _create_submission_bundle(
    session: Session,
    candidate: CandidateProfile,
    hiring_need: HiringNeed,
    task: Task,
    answer: str,
) -> Submission:
    submission = Submission(candidate_id=candidate.id, hiring_need_id=hiring_need.id, task_id=task.id, answer=answer)
    session.add(submission)
    session.flush()

    evaluation_output = evaluate_work_sample(
        answer=answer,
        task_competencies=task.competencies,
        priority_skills=hiring_need.criteria.get("priority_skills", []),
    )
    evaluation = AIEvaluation(
        submission=submission,
        raw_output=evaluation_output.model_dump(),
        parsed_json=evaluation_output.model_dump(),
        confidence=evaluation_output.confidence_band,
        safety_flags=[] if not evaluation_output.human_review_required else ["human_review_required"],
    )
    passport = SkillPassport(
        candidate=candidate,
        submission=submission,
        public_summary=build_passport_summary(evaluation_output, answer),
        strengths=evaluation_output.strengths,
        gaps=evaluation_output.gaps,
        evidence_preview=answer[:280],
    )
    session.add_all([evaluation, passport])
    candidate.visibility_status = (
        VisibilityStatus.employer_visible
        if evaluation_output.overall_score >= 70 and not evaluation_output.human_review_required
        else VisibilityStatus.needs_improvement
    )
    return submission


def _role_track_or_404(role_track_id: str):
    for track in role_tracks():
        if track.id == role_track_id:
            return track
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role track not found")


def _count_rows(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _get_hiring_need_or_404(session: Session, hiring_need_id: int) -> HiringNeed:
    result = session.execute(
        select(HiringNeed)
        .where(HiringNeed.id == hiring_need_id)
        .options(selectinload(HiringNeed.tasks), selectinload(HiringNeed.employer))
    )
    need = result.scalar_one_or_none()
    if need is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hiring need not found")
    return need


def _get_submission_or_404(session: Session, submission_id: int) -> Submission:
    result = session.execute(
        select(Submission)
        .where(Submission.id == submission_id)
        .options(
            selectinload(Submission.evaluation),
            selectinload(Submission.passport),
            selectinload(Submission.task),
            selectinload(Submission.candidate).selectinload(CandidateProfile.user),
        )
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")
    return submission


def _competency_coverage(task_competencies: list[str], parsed: dict) -> int:
    benchmark_scores = [
        parsed["skill_score"],
        parsed["evidence_score"],
        parsed["readiness_score"],
        parsed["role_fit_score"],
    ]
    score_factor = sum(1 for score in benchmark_scores if score >= 60) / len(benchmark_scores)
    breadth_factor = min(len(task_competencies) / 5, 1)
    return round((score_factor * 0.75 + breadth_factor * 0.25) * 100)
