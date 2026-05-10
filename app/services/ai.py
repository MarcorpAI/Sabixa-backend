from __future__ import annotations

import json
import os

from groq import AsyncGroq
from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas import EvaluationOutput, IntakeAnswers, RoleTrackRead, SkillMapItem

settings = get_settings()
client = AsyncGroq(api_key=settings.resolved_groq_api_key) if settings.resolved_groq_api_key else None

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


async def groq_complete(prompt: str, system: str = "You are a helpful assistant.") -> str | None:
    if not client:
        return None
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    try:
        resp = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
            timeout=8,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


async def evaluate_with_ai(
    answer: str, task: dict, priority_skills: list[str]
) -> EvaluationOutput | None:
    rubric = task.get("rubric", [])
    rubric_text = "\n".join(
        f"- {r.get('criterion', '')}: {r.get('description', '')} ({r.get('points', 0)} pts)"
        for r in rubric
    )

    prompt = f"""You are an expert customer support hiring evaluator. Score this candidate response only from the submitted work evidence.

Task: {task.get('title', '')}
Scenario: {task.get('scenario', '')}
Instructions: {task.get('instructions', '')}
Output format: {task.get('output_format', '')}

Rubric:
{rubric_text}

Priority skills for this role: {', '.join(priority_skills)}

Candidate response to evaluate:
---
{answer}
---

Scoring rules:
- Judge the exact candidate response against the task and rubric, not the candidate identity or background.
- Penalize answers that are too short, generic, off-task, overpromising, or missing required task elements.
- Every strength, gap, confidence reason, and rubric reason must be grounded in what the candidate wrote or omitted.
- Evidence quotes must be copied from the candidate response, not invented.
- If there is not enough evidence, use Low confidence and Not enough evidence.

Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{{
    "skill_scores": {{
        "empathy": <0-100>,
        "written_clarity": <0-100>,
        "complaint_handling": <0-100>,
        "escalation_judgement": <0-100>,
        "ownership": <0-100>,
        "follow_up_quality": <0-100>,
        "instruction_following": <0-100>,
        "professionalism": <0-100>
    }},
    "skill_score": <0-100>,
    "evidence_score": <0-100>,
    "readiness_score": <0-100>,
    "role_fit_score": <0-100>,
    "growth_score": <0-100>,
    "overall_score": <0-100>,
    "confidence_band": "Low" or "Medium" or "High",
    "confidence_reason": "<2 sentence explanation>",
    "rubric_breakdown": [
        {{"criterion": "<name>", "score": <0-100>, "critical": true/false, "reason": "<specific reason based on this answer>"}}
    ],
    "quoted_evidence": [
        {{"quote": "<verbatim quote from candidate answer>", "criterion": "<criterion>", "signal": "positive" or "negative", "note": "<why this quote matters>"}}
    ],
    "evidence_quotes": ["<1-2 key sentences from the answer>", "<second quote>"],
    "strengths": ["<specific strength 1>", "<specific strength 2>"],
    "gaps": [{{"competency": "<skill>", "description": "<specific gap>", "evidence": "<quote or missing element>"}}],
    "improvement_plan": [{{"gap": "<skill>", "action": "<specific practice action>", "resource_type": "practice_task"}}],
    "qa_checks": [{{"check": "<QA check name>", "passed": true/false, "action": "<publish or hold action>"}}],
    "human_review_required": true/false,
    "ethics_note": "AI scores submitted work evidence only. Human review remains required before hiring action.",
    "ethics_detail": {{"bias_check_passed": true, "factors_ignored": ["name", "school", "tribe", "gender", "age", "religion", "location", "disability"], "score_basis": "Score is based solely on task evidence.", "human_review_flagged": true/false, "uncertainty_disclosed": true}},
    "recommended_action": "Interview now" or "Give trial task" or "Add to pool" or "Improve first" or "Not enough evidence"
}}"""

    result = await groq_complete(
        prompt,
        system="""You are an expert customer support hiring evaluator. You score candidate work samples against clear rubrics. Always respond with valid JSON only, no markdown formatting. Be fair but discerning - look for real evidence of communication skills.""",
    )

    if not result:
        return None

    try:
        text = result.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        data = json.loads(text)

        return EvaluationOutput(
            skill_scores=data.get("skill_scores", {}),
            skill_score=data.get("skill_score", 50),
            evidence_score=data.get("evidence_score", 50),
            readiness_score=data.get("readiness_score", 50),
            role_fit_score=data.get("role_fit_score", 50),
            growth_score=data.get("growth_score", 50),
            overall_score=data.get("overall_score", 50),
            confidence_band=data.get("confidence_band", "Medium"),
            confidence_reason=data.get("confidence_reason", "Scoring complete."),
            rubric_breakdown=data.get("rubric_breakdown", []),
            quoted_evidence=data.get("quoted_evidence", []),
            evidence_quotes=data.get("evidence_quotes", []),
            strengths=data.get("strengths", []),
            gaps=data.get("gaps", []),
            improvement_plan=data.get("improvement_plan", []),
            qa_checks=data.get("qa_checks", []),
            human_review_required=data.get("human_review_required", False),
            ethics_note=ETHICS_NOTE,
            ethics_detail=data.get("ethics_detail", {}),
            recommended_action=data.get("recommended_action", "Improve first"),
        )
    except (json.JSONDecodeError, KeyError, ValidationError, TypeError):
        return None


async def generate_skill_map(answers: IntakeAnswers) -> list[SkillMapItem]:
    prompt = f"""Generate a customer support skill map based on this hiring need:

Why hiring now: {answers.why_hiring_now}
Company stage: {answers.company_stage}
Channels: {', '.join(answers.channels)}
Common issues: {answers.common_issues}
First 30 days: {answers.first_30_days}
Priority skills: {', '.join(answers.priority_skills)}

Return ONLY valid JSON (no markdown):
[{{"competency": "<skill name>", "why_it_matters": "<1 sentence>", "weight": <1-100>}}]

Include 6-8 key competencies relevant to this role."""

    result = await groq_complete(
        prompt,
        system="You are a hiring need analyst. Generate skill maps for customer support roles based on employer needs.",
    )

    if result:
        try:
            text = result.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            items = json.loads(text)
            return [SkillMapItem(**item) for item in items]
        except (json.JSONDecodeError, KeyError):
            pass

    return _default_skill_map(answers)


async def generate_tasks(answers: IntakeAnswers, skill_map: list[SkillMapItem]) -> list[dict]:
    competencies = [s.competency for s in skill_map]

    prompt = f"""Generate a 3-task assessment pack for customer support hiring.

Context:
- Company stage: {answers.company_stage}
- Channels: {', '.join(answers.channels)}
- Common issues: {answers.common_issues}
- First 30 days: {answers.first_30_days}
- Priority skills: {', '.join(answers.priority_skills)}

Required competencies: {', '.join(competencies)}

Return ONLY valid JSON (no markdown):
[{{
    "title": "<task name>",
    "scenario": "<realistic customer situation>",
    "instructions": "<what candidate must produce>",
    "output_format": "<message type>",
    "time_limit_minutes": <10-20>,
    "competencies": ["<skill1>", "<skill2>"],
    "rubric": [
        {{"criterion": "<name>", "description": "<what good looks like>", "points": <10-30>, "critical": true/false}}
    ]
}}]"""

    result = await groq_complete(
        prompt,
        system="You generate realistic customer support task scenarios for hiring assessments.",
    )

    if result:
        try:
            text = result.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            items = json.loads(text)
            return items
        except (json.JSONDecodeError, KeyError):
            pass

    return _default_task_pack(answers)


async def summarize_passport(evaluation: EvaluationOutput, answer: str) -> dict:
    strengths_text = ", ".join(_stringify_items(evaluation.strengths))
    gaps_text = ", ".join(_stringify_items(evaluation.gaps))
    prompt = f"""Create a skill passport summary from this evaluation.

Overall score: {evaluation.overall_score}/100
Confidence: {evaluation.confidence_band}
Strengths: {strengths_text}
Gaps: {gaps_text}

Answer preview: {answer[:200]}...

Return ONLY valid JSON:
{{
    "summary": "<2 sentence summary for non-technical reader>",
    "badge": "<one word: Ready, Promising, or Learning>",
    "headline": "<compelling 1 sentence>"
}}"""

    result = await groq_complete(prompt, system="You create candidate skill passport summaries.")

    if result:
        try:
            text = result.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
            return json.loads(text)
        except (json.JSONDecodeError,):
            pass

    return {"summary": f"Score: {evaluation.overall_score}/100", "badge": "Ready", "headline": "Assessment complete."}


def _stringify_items(items: list) -> list[str]:
    output = []
    for item in items:
        if isinstance(item, str):
            output.append(item)
        elif isinstance(item, dict):
            text = item.get("description") or item.get("action") or item.get("gap") or item.get("competency")
            if text:
                output.append(str(text))
        else:
            output.append(str(item))
    return output


def _default_skill_map(answers: IntakeAnswers) -> list[SkillMapItem]:
    base = [
        SkillMapItem(competency="Empathy", why_it_matters="Defuses upset customers", weight=92),
        SkillMapItem(competency="Written clarity", why_it_matters="Explains next steps clearly", weight=86),
        SkillMapItem(competency="Escalation judgement", why_it_matters="Knows when to involve supervisor", weight=80),
        SkillMapItem(competency="Ownership", why_it_matters="Takes responsibility", weight=74),
        SkillMapItem(competency="Follow-up quality", why_it_matters="Closes the loop", weight=68),
        SkillMapItem(competency="Complaint handling", why_it_matters="Moves upset customers toward resolution", weight=64),
        SkillMapItem(competency="Instruction-following", why_it_matters="Completes the requested format and constraints", weight=58),
    ]
    return sorted(base, key=lambda x: x.weight, reverse=True)


def _default_task_pack(answers: IntakeAnswers) -> list[dict]:
    from app.services.assessment import default_task_pack

    return default_task_pack(answers)
