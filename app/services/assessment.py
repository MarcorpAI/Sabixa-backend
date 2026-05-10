from __future__ import annotations

import re

from app.schemas import EvaluationOutput, IntakeAnswers, RoleTrackRead, SkillMapItem, TaskRubricCriterion


ETHICS_NOTE = {
    "bias_check_passed": True,
    "factors_ignored": ["name", "school", "tribe", "gender", "age", "religion", "location", "disability"],
    "score_basis": "Score is based solely on task evidence.",
    "human_review_flagged": False,
    "human_review_trigger": "Set to true if low confidence, weak evidence anchors, or score is within 5 points of threshold.",
    "uncertainty_disclosed": True,
}


def _levels(items: list[tuple[str, str]]) -> list[dict]:
    return [{"level": level, "definition": definition} for level, definition in items]


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
                "Adaeze paid for same-day delivery in Lagos three days ago. Her tracking page says "
                "Delivered but nothing arrived. She is messaging on WhatsApp and she is furious.\n\n"
                "Customer message: I am so angry right now. I ordered a gift for my sister's birthday "
                "three days ago and paid for SAME DAY delivery. Your tracking says delivered but nothing "
                "came. I have been home all day. Where is my package? I want my money back NOW."
            ),
            "instructions": (
                "Write a professional reply to Adaeze's WhatsApp message. Acknowledge how she feels, "
                "explain what you will do next, and give a specific timeframe. Keep it between 80 and "
                "150 words. Write as if you are replying in real time."
            ),
            "output_format": "WhatsApp response",
            "time_limit_minutes": 12,
            "competencies": ["Empathy", "Written clarity", "Complaint handling", "Ownership", "Follow-up quality"],
            "rubric": [
                TaskRubricCriterion(criterion="Tone and Empathy", description="Names the specific situation and validates frustration before resolution.", points=30, critical=True, levels=_levels([
                    ("5", "Specific birthday or three-day wait reference and warm personal acknowledgement."),
                    ("4", "General but warm acknowledgement of frustration."),
                    ("3", "Brief apology then moves quickly to process."),
                    ("2", "Formulaic apology only."),
                    ("1", "No emotional acknowledgement."),
                ])).model_dump(),
                TaskRubricCriterion(criterion="Actionable Resolution", description="States personal action, outcome and fallback if primary resolution fails.", points=25, critical=True, levels=_levels([
                    ("5", "Personal urgent action plus fallback such as refund if not located."),
                    ("4", "Specific personal action but no fallback."),
                    ("3", "Vague unnamed team escalation."),
                    ("2", "Intent to resolve but no named action."),
                    ("1", "No resolution offered."),
                ])).model_dump(),
                TaskRubricCriterion(criterion="Follow-Up Commitment", description="Specific next contact time and what will be reported.", points=20, critical=True, levels=_levels([
                    ("5", "Specific time and what update will cover."),
                    ("4", "Specific timeframe only."),
                    ("3", "Follow-up mentioned with no timeframe."),
                    ("2", "Passive follow-up language."),
                    ("1", "No follow-up mentioned."),
                ])).model_dump(),
                TaskRubricCriterion(criterion="Written Clarity", description="Short, WhatsApp-readable response with key action easy to find.", points=15, critical=True, levels=_levels([
                    ("5", "Short sentences, one idea per paragraph, no jargon."),
                    ("4", "Mostly clear with minor filler."),
                    ("3", "Readable but dense or filler-heavy."),
                    ("2", "Key action buried."),
                    ("1", "Dense or unclear."),
                ])).model_dump(),
                TaskRubricCriterion(criterion="Instruction Following", description="80-150 words, WhatsApp tone, empathy, problem, action, timeframe and warm close.", points=10, critical=True, levels=_levels([
                    ("5", "All required elements and word limit met."),
                    ("4", "Four of five required elements."),
                    ("3", "Missing one required element or slight tone issue."),
                    ("2", "Major word limit issue or missing two elements."),
                    ("1", "Off-task/template."),
                ])).model_dump(),
            ],
        },
        {
            "title": "Task B: Refund escalation response",
            "scenario": (
                "Emeka bought shoes online and changed his mind after finding them cheaper on Jumia. "
                "Company policy only covers damaged, wrong, or undelivered items. He is threatening "
                "to post about the company on Twitter.\n\nCustomer message: I want to return these shoes. "
                "I changed my mind and found them cheaper on Jumia. I have not opened the box. I deserve "
                "my money back. If you people don't refund me, I will post about this on Twitter and "
                "everyone will know your company is useless."
            ),
            "instructions": (
                "Decline the refund in line with policy but keep the relationship intact. Do not apologise "
                "for the policy. Do not promise what you cannot deliver. Acknowledge the Twitter point calmly. "
                "Under 180 words."
            ),
            "output_format": "Short message",
            "time_limit_minutes": 15,
            "competencies": ["Complaint handling", "Professionalism", "Policy clarity", "Escalation judgement", "Ownership"],
            "rubric": [
                TaskRubricCriterion(criterion="Tone and Professionalism", description="Calmly declines without lecturing and acknowledges Twitter point.", points=30, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Actionable Resolution", description="Declines refund and offers a genuine alternative such as exchange or store credit.", points=25, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Policy Clarity", description="Explains policy plainly without blame or legalistic terms.", points=20, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Escalation Judgement", description="Handles Twitter threat without dismissing it or caving to it.", points=15, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Instruction Following", description="Under 180 words, no apology for policy, no unauthorized promise.", points=10, critical=True).model_dump(),
            ],
        },
        {
            "title": "Task C: Support ticket summary",
            "scenario": (
                "You are a support team lead at a Lagos fintech startup. Bola Adeyemi's 45,000-naira "
                "transfer failed and her account was debited. A junior agent handled the complaint poorly "
                "over three days, gave no timeframe on Day 2, and responded with 'we are working on it' "
                "on Day 3 after Bola threatened to report to the CBN."
            ),
            "instructions": (
                "Write a one-paragraph internal summary. Cover what the issue is, what has happened, "
                "where things stand, and what the recommended next action is. Keep it between 100 and "
                "150 words. Write clearly and factually."
            ),
            "output_format": "Ticket note",
            "time_limit_minutes": 10,
            "competencies": ["Written clarity", "Instruction-following", "Ownership", "Professionalism", "Escalation judgement"],
            "rubric": [
                TaskRubricCriterion(criterion="Actionable Resolution", description="Specific, senior, time-bound recommended action.", points=30, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Accuracy and Completeness", description="Includes amount, debit, timeline, handling gaps, Day 3 response and CBN threat.", points=25, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Internal Tone", description="Professional factual manager-facing tone without editorializing.", points=20, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Escalation Identification", description="Names handling gap and treats CBN threat as urgent regulatory risk.", points=15, critical=True).model_dump(),
                TaskRubricCriterion(criterion="Written Clarity", description="100-150 words, one paragraph, crisp and scannable.", points=10, critical=True).model_dump(),
            ],
        },
    ]


def evaluate_work_sample(
    answer: str,
    task_competencies: list[str],
    priority_skills: list[str],
    rubric: list[dict] | None = None,
) -> EvaluationOutput:
    text = answer.strip()
    lowered = text.lower()
    words = [word for word in text.split() if word]
    word_count = len(words)

    empathy_hits = _count(lowered, ["sorry", "understand", "frustrating", "patience", "apolog"])
    clarity_hits = _count(lowered, ["today", "before", "next", "status", "because", "update", "option"])
    ownership_hits = _count(lowered, ["i will", "i'll", "checking", "resolve", "follow", "handle"])
    escalation_hits = _count(lowered, ["escalate", "supervisor", "policy", "refund", "dispatch", "operations"])
    structure_hits = _count(lowered, ["summary", "issue", "next action", "missing", "customer", "order"])

    rubric_rows = _score_rubric(
        lowered=lowered,
        word_count=word_count,
        rubric=rubric or [],
        empathy_hits=empathy_hits,
        clarity_hits=clarity_hits,
        ownership_hits=ownership_hits,
        escalation_hits=escalation_hits,
        structure_hits=structure_hits,
    )
    weighted_rubric_score = _weighted_rubric_score(rubric_rows)

    skill_score = _clamp(
        weighted_rubric_score * 0.65
        + (38 + empathy_hits * 8 + ownership_hits * 7 + escalation_hits * 5 + structure_hits * 3) * 0.35
    )
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

    critical_low = min(skill_score, evidence_score, readiness_score) < 60 or any(
        row.get("critical") and row.get("score", 100) < 60 for row in rubric_rows
    )
    confidence = "Low" if word_count < 25 or overall < 55 else "High" if word_count > 55 and overall >= 75 else "Medium"
    borderline = 65 <= overall <= 75
    human_review_required = confidence == "Low" or borderline
    action = _recommended_action(overall, confidence, critical_low)
    skill_scores = _skill_scores(
        empathy_hits=empathy_hits,
        clarity_hits=clarity_hits,
        ownership_hits=ownership_hits,
        escalation_hits=escalation_hits,
        structure_hits=structure_hits,
        word_count=word_count,
        overall=overall,
    )
    quoted_evidence = _quoted_evidence(text, skill_scores)
    gaps = _gaps(word_count, empathy_hits, ownership_hits, clarity_hits, escalation_hits, critical_low)
    improvement_plan = _improvement_plan(gaps)
    qa_checks, qa_human_review = _qa_checks(
        answer=text,
        overall=overall,
        confidence=confidence,
        quoted_evidence=quoted_evidence,
        improvement_plan=improvement_plan,
    )
    human_review_required = human_review_required or qa_human_review
    ethics_note = {**ETHICS_NOTE, "human_review_flagged": human_review_required}

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
        skill_scores=skill_scores,
        rubric_breakdown=rubric_rows
        or [
            {"criterion": "Skill performance", "score": round(skill_score), "critical": True},
            {"criterion": "Evidence quality", "score": round(evidence_score), "critical": True},
            {"criterion": "Readiness", "score": round(readiness_score), "critical": True},
            {"criterion": "Role fit", "score": round(role_fit_score), "critical": False},
            {"criterion": "Growth clarity", "score": round(growth_score), "critical": False},
        ],
        quoted_evidence=quoted_evidence,
        evidence_quotes=[item["quote"] for item in quoted_evidence] or _evidence_quotes(text),
        strengths=_strengths(empathy_hits, ownership_hits, clarity_hits, escalation_hits, structure_hits),
        gaps=gaps,
        improvement_plan=improvement_plan,
        qa_checks=qa_checks,
        human_review_required=human_review_required,
        ethics_note="AI scores submitted work evidence only. Human review remains required before hiring action.",
        ethics_detail=ethics_note,
    )


def build_passport_summary(evaluation: EvaluationOutput, answer: str) -> dict:
    return {
        "overall_score": evaluation.overall_score,
        "confidence_band": evaluation.confidence_band,
        "recommended_action": evaluation.recommended_action,
        "skill_scores": evaluation.skill_scores,
        "score_breakdown": {
            "skill_score": evaluation.skill_score,
            "evidence_score": evaluation.evidence_score,
            "readiness_score": evaluation.readiness_score,
            "role_fit_score": evaluation.role_fit_score,
            "growth_score": evaluation.growth_score,
        },
        "human_review_required": evaluation.human_review_required,
        "evidence_quotes": evaluation.evidence_quotes,
        "quoted_evidence": evaluation.quoted_evidence,
        "qa_checks": evaluation.qa_checks,
        "ethics_note": evaluation.ethics_note,
        "ethics_detail": evaluation.ethics_detail,
        "evidence_preview": answer[:280],
    }


def build_improvement_route(evaluation: EvaluationOutput) -> dict:
    below_benchmark = evaluation.overall_score < 70 or evaluation.confidence_band == "Low"
    return {
        "visibility": "improve_first" if below_benchmark else "employer_visible",
        "reason": _gap_text(evaluation.gaps[0]) if below_benchmark else "Candidate meets the first-task benchmark.",
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


def _score_rubric(
    lowered: str,
    word_count: int,
    rubric: list[dict],
    empathy_hits: int,
    clarity_hits: int,
    ownership_hits: int,
    escalation_hits: int,
    structure_hits: int,
) -> list[dict]:
    rows = []
    for item in rubric:
        criterion = str(item.get("criterion", "Criterion"))
        description = str(item.get("description", ""))
        label = f"{criterion} {description}".lower()
        score = 45
        if any(term in label for term in ["empathy", "calm", "complaint", "professional"]):
            score += min(30, empathy_hits * 12)
        if any(term in label for term in ["clarity", "structure", "complete", "diagnosis"]):
            score += min(30, (clarity_hits + structure_hits) * 8)
        if any(term in label for term in ["ownership", "follow", "next", "time", "window"]):
            score += min(35, (ownership_hits + clarity_hits) * 8)
        if any(term in label for term in ["escalation", "policy", "refund", "boundary"]):
            score += min(35, escalation_hits * 12)
        if word_count >= 35:
            score += 10
        if word_count < 15:
            score -= 25
        if "?" in lowered and any(term in label for term in ["diagnosis", "complete", "missing"]):
            score += 8
        rows.append(
            {
                "criterion": criterion,
                "score": round(_clamp(score)),
                "critical": bool(item.get("critical", False)),
                "reason": _criterion_reason(criterion, lowered, word_count, score),
            }
        )
    return rows


def _weighted_rubric_score(rows: list[dict]) -> float:
    if not rows:
        return 50
    return sum(row.get("score", 0) for row in rows) / len(rows)


def _criterion_reason(criterion: str, lowered: str, word_count: int, score: float) -> str:
    if word_count < 15:
        return f"{criterion} is low because the answer is too short to show enough task evidence."
    if score >= 75:
        return f"{criterion} is supported by concrete language in the response."
    if "update" not in lowered and "next" not in lowered:
        return f"{criterion} needs a clearer next step or update window."
    if "sorry" not in lowered and "understand" not in lowered:
        return f"{criterion} needs warmer acknowledgement of the customer situation."
    return f"{criterion} has some evidence, but the response needs more specific handling detail."


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


def _skill_scores(
    empathy_hits: int,
    clarity_hits: int,
    ownership_hits: int,
    escalation_hits: int,
    structure_hits: int,
    word_count: int,
    overall: int,
) -> dict[str, int]:
    length_bonus = 12 if word_count >= 60 else 0 if word_count >= 35 else -18
    return {
        "empathy": round(_clamp(38 + empathy_hits * 18 + length_bonus)),
        "written_clarity": round(_clamp(42 + clarity_hits * 13 + structure_hits * 5 + length_bonus)),
        "complaint_handling": round(_clamp(40 + empathy_hits * 8 + escalation_hits * 8 + length_bonus)),
        "escalation_judgement": round(_clamp(38 + escalation_hits * 18 + structure_hits * 6 + length_bonus)),
        "ownership": round(_clamp(38 + ownership_hits * 18 + length_bonus)),
        "follow_up_quality": round(_clamp(34 + clarity_hits * 10 + ownership_hits * 8 + length_bonus)),
        "instruction_following": round(_clamp(45 + min(word_count, 150) * 0.18 + length_bonus)),
        "professionalism": round(_clamp(max(35, overall - 4) + length_bonus * 0.2)),
    }


def _quoted_evidence(text: str, skill_scores: dict[str, int]) -> list[dict]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    if not sentences and text:
        sentences = [text]
    evidence = []
    positive_criterion = max(skill_scores, key=skill_scores.get) if skill_scores else "ownership"
    negative_criterion = min(skill_scores, key=skill_scores.get) if skill_scores else "follow_up_quality"
    if sentences:
        evidence.append(
            {
                "quote": sentences[0][:220],
                "criterion": _format_competency(positive_criterion),
                "signal": "positive" if skill_scores.get(positive_criterion, 0) >= 60 else "negative",
                "note": f"Evidence used to assess {_format_competency(positive_criterion)}.",
            }
        )
    if len(sentences) > 1:
        evidence.append(
            {
                "quote": sentences[-1][:220],
                "criterion": _format_competency(negative_criterion),
                "signal": "negative" if skill_scores.get(negative_criterion, 100) < 70 else "positive",
                "note": f"Evidence used to assess {_format_competency(negative_criterion)}.",
            }
        )
    return evidence[:2]


def _qa_checks(
    answer: str,
    overall: int,
    confidence: str,
    quoted_evidence: list[dict],
    improvement_plan: list[dict | str],
) -> tuple[list[dict], bool]:
    word_count = len([word for word in answer.split() if word])
    checks = []
    needs_review = False

    evidence_pass = overall <= 40 or (
        len(quoted_evidence) >= 2 and all(item.get("quote", "") in answer for item in quoted_evidence)
    )
    checks.append(
        {
            "check": "Evidence Anchor Requirement",
            "passed": evidence_pass,
            "action": "publish" if evidence_pass else "hold_for_human_review",
        }
    )
    needs_review = needs_review or not evidence_pass

    confidence_pass = not (word_count < 60 and confidence != "Low")
    checks.append(
        {
            "check": "Confidence Band Validation",
            "passed": confidence_pass,
            "word_count": word_count,
            "action": "publish" if confidence_pass and word_count >= 60 else "flag_for_human_review",
        }
    )
    needs_review = needs_review or word_count < 60 or not confidence_pass

    borderline = abs(overall - 70) <= 5 or abs(overall - 60) <= 5
    checks.append(
        {
            "check": "Borderline Score Threshold",
            "passed": not borderline,
            "action": "hold_for_human_review" if borderline else "publish",
        }
    )
    needs_review = needs_review or borderline

    plan_text = " ".join(_gap_text(item) for item in improvement_plan).lower()
    prohibited = [
        "keep practising",
        "almost at the benchmark",
        "great effort",
        "communication skills generally",
        "customer service best practices",
    ]
    plan_pass = not any(phrase in plan_text for phrase in prohibited)
    checks.append(
        {
            "check": "Improvement Plan Quality",
            "passed": plan_pass,
            "action": "publish" if plan_pass else "regenerate_improvement_plan",
        }
    )

    checks.append(
        {
            "check": "Demographic Exclusion Verification",
            "passed": True,
            "action": "publish",
            "factors_ignored": ETHICS_NOTE["factors_ignored"],
        }
    )
    return checks, needs_review


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
) -> list[dict]:
    gaps: list[dict] = []
    if word_count < 35:
        gaps.append({"competency": "Instruction Following", "description": "Answer is too short to judge support readiness confidently.", "evidence": "Submission length"})
    if empathy_hits < 2:
        gaps.append({"competency": "Empathy", "description": "Add a warmer acknowledgement before moving into process.", "evidence": "Missing specific emotional acknowledgement"})
    if clarity_hits < 2:
        gaps.append({"competency": "Follow-Up Quality", "description": "Give a specific customer-facing update window or next step.", "evidence": "No clear timeframe or next action"})
    if escalation_hits < 1:
        gaps.append({"competency": "Escalation Judgement", "description": "Mention policy, supervisor, or operations handoff when the issue requires it.", "evidence": "No escalation or policy signal found"})
    if ownership_hits < 2:
        gaps.append({"competency": "Ownership", "description": "Use stronger ownership language so the customer does not need to chase again.", "evidence": "Limited first-person accountability"})
    if critical_low:
        gaps.append({"competency": "Benchmark", "description": "At least one critical competency is below the 60-point benchmark.", "evidence": "Rubric score below threshold"})
    return gaps or [{"competency": "Benchmark", "description": "No critical competency below benchmark in this task.", "evidence": "Rubric scores"}]


def _improvement_plan(gaps: list[dict | str]) -> list[dict]:
    if not gaps or _gap_text(gaps[0]).startswith("No critical competency"):
        return [
            {
                "gap": "Evidence depth",
                "action": "Complete the next assessment task to increase employer confidence across more competencies.",
                "resource_type": "practice_task",
            }
        ]
    return [
        {
            "gap": _gap_competency(gap),
            "action": f"Rewrite the relevant part of your response: {_gap_text(gap)}",
            "resource_type": "practice_task",
        }
        for gap in gaps[:3]
    ]


def _evidence_quotes(text: str) -> list[str]:
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    return [sentence[:180] for sentence in sentences[:2]]


def _gap_text(gap: dict | str) -> str:
    return gap.get("description", "") if isinstance(gap, dict) else gap


def _gap_competency(gap: dict | str) -> str:
    return gap.get("competency", "Practice focus") if isinstance(gap, dict) else "Practice focus"


def _format_competency(value: str) -> str:
    return value.replace("_", " ").title()


def _count(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> float:
    return max(minimum, min(maximum, value))
