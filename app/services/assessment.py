from __future__ import annotations

import re

from app.schemas import EvaluationOutput, IntakeAnswers, RoleTrackRead, SkillMapItem, TaskRubricCriterion


ETHICS_NOTE = "AI scores submitted work evidence only. Human review remains required before hiring action."


def role_tracks() -> list[RoleTrackRead]:
    return [
        RoleTrackRead(
            id="customer-support-associate",
            title="Customer Support Associate",
            role_family="Customer support / customer operations",
            summary="Prove you can respond clearly, handle complaints, escalate well and follow up.",
            task_count=3,
            benchmark="2 tasks with 70+ average and no critical skill below 60",
            competencies=[
                "Empathy",
                "Written clarity",
                "Complaint handling",
                "Escalation judgement",
                "Ownership",
                "Follow-up quality",
                "Instruction-following",
                "Professionalism",
            ],
        )
    ]


def build_role_problem_summary(answers: IntakeAnswers, rough_jd: str | None) -> str:
    jd_hint = f" The rough JD adds: {rough_jd.strip()}" if rough_jd else ""
    return (
        f"{answers.company_stage} needs an entry-level customer support hire because "
        f"{answers.why_hiring_now}. The person will handle {', '.join(answers.channels)} "
        f"issues such as {answers.common_issues}, with early responsibility for "
        f"{answers.first_30_days}.{jd_hint}"
    )


def build_skill_map(answers: IntakeAnswers) -> list[SkillMapItem]:
    competency_notes = {
        "Empathy": "Defuses upset customers and acknowledges frustration without sounding scripted.",
        "Clarity": "Explains status, policy, and next steps in simple customer-facing language.",
        "Escalation judgement": "Knows when a refund, delivery, or policy case needs supervisor handoff.",
        "Speed": "Responds quickly while still protecting accuracy and tone.",
        "Accuracy": "Captures customer facts, order details, and policy boundaries correctly.",
        "Ownership": "Takes responsibility for follow-up instead of leaving the customer to chase again.",
        "Follow-up quality": "Sets realistic update windows and closes the loop after escalation.",
        "Complaint handling": "Keeps calm under pressure and moves the customer toward resolution.",
    }
    base_order = [
        "Empathy",
        "Clarity",
        "Escalation judgement",
        "Ownership",
        "Accuracy",
        "Follow-up quality",
        "Complaint handling",
        "Speed",
    ]
    priorities = set(answers.priority_skills)
    items: list[SkillMapItem] = []
    for index, competency in enumerate(base_order):
        priority_boost = 16 if competency in priorities else 0
        weight = max(45, 92 - index * 6 + priority_boost)
        items.append(
            SkillMapItem(
                competency=competency,
                why_it_matters=competency_notes[competency],
                weight=min(weight, 100),
            )
        )
    return sorted(items, key=lambda item: item.weight, reverse=True)


def build_criteria(answers: IntakeAnswers) -> dict:
    return {
        "minimum_employer_ready_tasks": 2,
        "strong_confidence_tasks": 3,
        "overall_benchmark": 70,
        "critical_competency_floor": 60,
        "priority_skills": answers.priority_skills,
        "human_review_rule": "Low confidence requires human review regardless of score.",
        "pass_rules": {
            "80-100": "Strong employer-ready evidence. Recommend interview or trial task.",
            "70-79": "Promising and shortlist-worthy if no critical competency is below 60.",
            "60-69": "Talent pool after improvement route.",
            "below_60": "Improve first before employer visibility.",
        },
    }


def default_task_pack(answers: IntakeAnswers) -> list[dict]:
    return [
        {
            "title": "Task A: Delayed delivery complaint",
            "scenario": (
                "Customer paid for same-day delivery, tracking says delivered, the package is missing, "
                "and the customer demands a refund."
            ),
            "instructions": "Write a WhatsApp response within 150 words. Acknowledge the issue, take ownership, give a clear next step and timeframe.",
            "output_format": "WhatsApp response",
            "time_limit_minutes": 15,
            "competencies": ["Empathy", "Written clarity", "Complaint handling", "Ownership", "Follow-up quality"],
            "rubric": [
                TaskRubricCriterion(
                    criterion="Empathy",
                    description="Acknowledges frustration without blaming the customer.",
                    points=20,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Written clarity",
                    description="Explains what happens next in simple language.",
                    points=20,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Ownership",
                    description="Takes responsibility for checking, updating, or escalating.",
                    points=25,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Follow-up quality",
                    description="Gives a realistic action or update window.",
                    points=25,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Professionalism",
                    description="Uses calm tone and avoids defensive language.",
                    points=10,
                ).model_dump(),
            ],
        },
        {
            "title": "Task B: Refund escalation response",
            "scenario": "Customer wants a refund for change of mind although policy does not allow it, and threatens Twitter escalation.",
            "instructions": "Write a firm but respectful response. Keep the customer calm, explain the policy boundary and offer an alternative next step.",
            "output_format": "Short message",
            "time_limit_minutes": 15,
            "competencies": ["Complaint handling", "Professionalism", "Policy clarity", "Escalation judgement", "Ownership"],
            "rubric": [
                TaskRubricCriterion(
                    criterion="Escalation judgement",
                    description="Recognises the need for policy or supervisor review.",
                    points=30,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Calmness",
                    description="Responds without arguing about the threatened review.",
                    points=20,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Policy clarity",
                    description="Explains a credible path to resolution.",
                    points=20,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Professionalism",
                    description="Keeps tone respectful and brand-safe.",
                    points=20,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Policy boundary",
                    description="Avoids promising an outcome outside policy.",
                    points=10,
                    critical=True,
                ).model_dump(),
            ],
        },
        {
            "title": "Task C: Support ticket summary",
            "scenario": "Failed fintech transfer complaint has dragged for three days and customer threatens CBN escalation.",
            "instructions": "Create an internal ticket note with issue summary, facts, handling gap, urgency, missing details and next action.",
            "output_format": "Ticket note",
            "time_limit_minutes": 15,
            "competencies": ["Written clarity", "Problem diagnosis", "Instruction-following", "Escalation judgement", "Professionalism"],
            "rubric": [
                TaskRubricCriterion(
                    criterion="Problem diagnosis",
                    description="Identifies the real issue and separates facts from assumptions.",
                    points=30,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Structure",
                    description="Organises notes so a supervisor can act quickly.",
                    points=25,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Completeness",
                    description="Includes relevant customer details and missing information.",
                    points=25,
                    critical=True,
                ).model_dump(),
                TaskRubricCriterion(
                    criterion="Follow-up quality",
                    description="Recommends a clear next action or customer update.",
                    points=20,
                ).model_dump(),
            ],
        },
    ]


def evaluate_work_sample(answer: str, task_competencies: list[str], priority_skills: list[str]) -> EvaluationOutput:
    text = answer.strip()
    lowered = text.lower()
    words = [word for word in text.split() if word]
    word_count = len(words)

    empathy_hits = _count(lowered, ["sorry", "understand", "frustrating", "patience", "apolog"])
    clarity_hits = _count(lowered, ["today", "before", "next", "status", "because", "update", "option"])
    ownership_hits = _count(lowered, ["i will", "i'll", "checking", "resolve", "follow", "handle"])
    escalation_hits = _count(lowered, ["escalate", "supervisor", "policy", "refund", "dispatch", "operations"])
    structure_hits = _count(lowered, ["summary", "issue", "next action", "missing", "customer", "order"])

    skill_score = _clamp(38 + empathy_hits * 8 + ownership_hits * 7 + escalation_hits * 5 + structure_hits * 3)
    evidence_score = _clamp(32 + clarity_hits * 8 + structure_hits * 5 + min(word_count, 90) * 0.28)
    readiness_score = _clamp(40 + empathy_hits * 5 + clarity_hits * 5 + (18 if word_count >= 35 else 0))
    role_fit_score = _clamp(42 + len(set(task_competencies).intersection(priority_skills)) * 5 + escalation_hits * 6)
    growth_score = _clamp(78 - max(0, 45 - word_count) * 0.75 + clarity_hits * 2)
    overall = round(
        skill_score * 0.3
        + evidence_score * 0.22
        + readiness_score * 0.2
        + role_fit_score * 0.18
        + growth_score * 0.1
    )

    critical_low = min(skill_score, evidence_score, readiness_score) < 60
    confidence = "Low" if word_count < 25 or overall < 55 else "High" if word_count > 55 and overall >= 75 else "Medium"
    borderline = 65 <= overall <= 75
    human_review_required = confidence == "Low" or borderline
    action = _recommended_action(overall, confidence, critical_low)
    gaps = _gaps(word_count, empathy_hits, ownership_hits, clarity_hits, escalation_hits, critical_low)

    return EvaluationOutput(
        overall_score=overall,
        skill_score=round(skill_score),
        evidence_score=round(evidence_score),
        readiness_score=round(readiness_score),
        role_fit_score=round(role_fit_score),
        growth_score=round(growth_score),
        confidence_band=confidence,
        confidence_reason=_confidence_reason(confidence, word_count, overall, borderline),
        recommended_action=action,
        rubric_breakdown=[
            {"criterion": "Skill performance", "score": round(skill_score), "critical": True},
            {"criterion": "Evidence quality", "score": round(evidence_score), "critical": True},
            {"criterion": "Readiness", "score": round(readiness_score), "critical": True},
            {"criterion": "Role fit", "score": round(role_fit_score), "critical": False},
            {"criterion": "Growth clarity", "score": round(growth_score), "critical": False},
        ],
        evidence_quotes=_evidence_quotes(text),
        strengths=_strengths(empathy_hits, ownership_hits, clarity_hits, escalation_hits, structure_hits),
        gaps=gaps,
        improvement_plan=_improvement_plan(gaps),
        human_review_required=human_review_required,
        ethics_note=ETHICS_NOTE,
    )


def build_passport_summary(evaluation: EvaluationOutput, answer: str) -> dict:
    return {
        "overall_score": evaluation.overall_score,
        "confidence_band": evaluation.confidence_band,
        "recommended_action": evaluation.recommended_action,
        "score_breakdown": {
            "skill_score": evaluation.skill_score,
            "evidence_score": evaluation.evidence_score,
            "readiness_score": evaluation.readiness_score,
            "role_fit_score": evaluation.role_fit_score,
            "growth_score": evaluation.growth_score,
        },
        "human_review_required": evaluation.human_review_required,
        "evidence_quotes": evaluation.evidence_quotes,
        "ethics_note": evaluation.ethics_note,
        "evidence_preview": answer[:280],
    }


def build_improvement_route(evaluation: EvaluationOutput) -> dict:
    below_benchmark = evaluation.overall_score < 70 or evaluation.confidence_band == "Low"
    return {
        "visibility": "improve_first" if below_benchmark else "employer_visible",
        "reason": evaluation.gaps[0] if below_benchmark else "Candidate meets the first-task benchmark.",
        "recommended_next_task": (
            "Rewrite the response with warmer acknowledgement, a clear update window, and escalation path."
            if below_benchmark
            else "Complete a second task to reach the employer-ready benchmark."
        ),
        "practice_focus": evaluation.gaps,
        "improvement_plan": evaluation.improvement_plan,
        "retry_allowed": True,
        "human_review_note": "Low confidence or borderline results should be reviewed by a human before action.",
    }


def task_count_readiness(task_scores: list[int], has_critical_low: bool, has_low_confidence: bool) -> dict:
    task_count = len(task_scores)
    average = round(sum(task_scores) / task_count) if task_scores else 0
    if task_count == 0:
        label = "No evidence"
        action = "Not enough evidence"
    elif task_count == 1:
        label = "Early signal"
        action = "Review another task"
    elif average >= 70 and not has_critical_low and not has_low_confidence and task_count >= 3:
        label = "Strong shortlist confidence"
        action = "Interview now"
    elif average >= 70 and not has_critical_low and not has_low_confidence:
        label = "Employer-ready benchmark"
        action = "Give trial task"
    elif average < 60:
        label = "Improve first"
        action = "Improve first"
    else:
        label = "Borderline"
        action = "Human review required"
    return {"task_count": task_count, "average_score": average, "readiness_label": label, "recommended_action": action}


def reconcile_trial_task(trial_task_text: str, assessment_tasks: list[dict]) -> dict:
    trial_text = trial_task_text.lower()
    task_text = " ".join(
        f"{task.get('title', '')} {task.get('scenario', '')} {' '.join(task.get('competencies', []))}"
        for task in assessment_tasks
    ).lower()
    competency_terms = {
        "Empathy": ["empathy", "acknowledge", "frustration", "calm"],
        "Written clarity": ["write", "message", "response", "summary", "clarity"],
        "Complaint handling": ["complaint", "angry", "threat", "escalation"],
        "Escalation judgement": ["escalate", "supervisor", "urgent", "cbn", "twitter"],
        "Ownership": ["follow up", "update", "resolve", "own"],
        "Follow-up quality": ["timeframe", "callback", "next step", "close the loop"],
        "Policy clarity": ["policy", "refund", "allowed", "not allow"],
        "Product knowledge": ["product", "company", "internal", "process", "tool"],
    }
    repeated = []
    new = []
    for competency, terms in competency_terms.items():
        in_trial = any(term in trial_text for term in terms)
        in_pack = any(term in task_text for term in terms)
        if in_trial and in_pack:
            repeated.append(competency)
        elif in_trial:
            new.append(competency)

    overlap_score = min(100, round((len(repeated) / max(len(repeated) + len(new), 1)) * 100))
    if overlap_score >= 75:
        recommendation = "Replace"
        suggestion = "Use a trial task that tests company-specific process, product rules or internal tools instead of another support response."
    elif overlap_score >= 45:
        recommendation = "Adjust"
        suggestion = "Keep the trial task but add company policy, product detail or internal handoff requirements."
    else:
        recommendation = "Keep"
        suggestion = "This trial task adds enough new company-specific evidence to keep after Sabixa screening."

    return {
        "overlap_score": overlap_score,
        "repeated_competencies": repeated,
        "new_competencies": new or ["Company-specific process"],
        "recommendation": recommendation,
        "suggested_adjustment": suggestion,
    }


def _recommended_action(overall: int, confidence: str, critical_low: bool) -> str:
    if confidence == "Low":
        return "Not enough evidence"
    if overall >= 80:
        return "Interview now"
    if overall >= 70 and not critical_low:
        return "Give trial task"
    if overall >= 60:
        return "Add to pool"
    return "Improve first"


def _confidence_reason(confidence: str, word_count: int, overall: int, borderline: bool) -> str:
    if confidence == "Low":
        return "Submission is short or weak enough that human review is needed."
    if borderline:
        return "Score is close to a benchmark threshold, so a reviewer should verify the evidence."
    if confidence == "High":
        return "Submission has enough detail and score strength for higher confidence."
    return "Submission has usable evidence but another task would improve confidence."


def _strengths(
    empathy_hits: int, ownership_hits: int, clarity_hits: int, escalation_hits: int, structure_hits: int
) -> list[str]:
    strengths = []
    if empathy_hits >= 2:
        strengths.append("Shows empathy and acknowledges customer frustration.")
    if ownership_hits >= 2:
        strengths.append("Takes ownership through follow-up or resolution language.")
    if clarity_hits >= 2:
        strengths.append("Gives clear next steps or timing.")
    if escalation_hits >= 1:
        strengths.append("Recognises when escalation, policy, or operations support matters.")
    if structure_hits >= 2:
        strengths.append("Organises customer facts in a way a supervisor can act on.")
    return strengths or ["Submission is relevant to the task, but evidence is still thin."]


def _gaps(
    word_count: int,
    empathy_hits: int,
    ownership_hits: int,
    clarity_hits: int,
    escalation_hits: int,
    critical_low: bool,
) -> list[str]:
    gaps = []
    if word_count < 35:
        gaps.append("Answer is too short to judge support readiness confidently.")
    if empathy_hits < 2:
        gaps.append("Add a warmer acknowledgement before moving into process.")
    if clarity_hits < 2:
        gaps.append("Give a specific customer-facing update window or next step.")
    if escalation_hits < 1:
        gaps.append("Mention policy, supervisor, or operations handoff when the issue requires it.")
    if ownership_hits < 2:
        gaps.append("Use stronger ownership language so the customer does not need to chase again.")
    if critical_low:
        gaps.append("At least one critical competency is below the 60-point benchmark.")
    return gaps or ["No critical competency below benchmark in this task."]


def _improvement_plan(gaps: list[str]) -> list[str]:
    if not gaps or gaps == ["No critical competency below benchmark in this task."]:
        return ["Complete the next assessment task to increase employer confidence."]
    return [f"Practice focus: {gap}" for gap in gaps[:3]]


def _evidence_quotes(text: str) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    return [sentence[:180] for sentence in sentences[:2]]


def _count(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> float:
    return max(minimum, min(maximum, value))
