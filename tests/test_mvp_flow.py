from __future__ import annotations

import importlib

import httpx
import pytest


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sabixa-test.db"
    monkeypatch.setenv("SABIXA_DATABASE_URL", f"sqlite:///{db_path}")

    import app.core.config as config
    import app.db.session as db_session
    import app.db.init_db as init_db_module
    import app.main as main_module

    config.get_settings.cache_clear()
    importlib.reload(db_session)
    importlib.reload(init_db_module)
    importlib.reload(main_module)

    transport = httpx.ASGITransport(app=main_module.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


async def test_health(client: httpx.AsyncClient):
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_mvp_status_exposes_prd_backend_coverage(client: httpx.AsyncClient):
    response = await client.get("/api/v1/mvp/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sprint_scope"]["employer_hiring_need_intake"] is True
    assert payload["sprint_scope"]["ai_skill_map_and_3_task_pack"] is True
    assert payload["sprint_scope"]["pitch_deck_content"] is False
    assert len(payload["acceptance_criteria"]) == 11
    assert payload["sprint_scope"]["trial_task_reconciliation"] is True
    assert payload["sprint_scope"]["simple_prototype_auth"] is True
    assert "POST /api/v1/submissions" in {
        item["primary_endpoint"] for item in payload["acceptance_criteria"]
    }
    assert "POST /api/v1/trial-task-reconcile" in {
        item["primary_endpoint"] for item in payload["acceptance_criteria"]
    }


async def test_role_track_and_candidate_auth_onboard_candidate(client: httpx.AsyncClient):
    tracks_response = await client.get("/api/v1/role-tracks")
    assert tracks_response.status_code == 200
    tracks = tracks_response.json()
    assert tracks[0]["id"] == "customer-support-associate"
    assert tracks[0]["task_count"] == 3

    auth_response = await client.post(
        "/api/v1/auth/candidate",
        json={
            "full_name": "New Candidate",
            "email": "newcandidate@example.com",
            "location": "Lagos, Nigeria",
            "experience": "Handled WhatsApp messages for a small business.",
            "role_track_id": "customer-support-associate",
        },
    )
    assert auth_response.status_code == 201
    payload = auth_response.json()
    assert payload["candidate"]["role_interest"] == "Customer Support Associate"
    assert payload["role_track"]["title"] == "Customer Support Associate"


async def test_demo_seed_builds_frontend_ready_scenario(client: httpx.AsyncClient):
    seed_response = await client.post("/api/v1/demo/seed")

    assert seed_response.status_code == 201
    seed = seed_response.json()
    assert seed["employer_id"] > 0
    assert len(seed["candidate_ids"]) == 3
    assert len(seed["task_ids"]) == 3
    assert len(seed["submission_ids"]) == 3
    assert len(seed["passport_ids"]) == 3
    assert len(seed["shortlist"]) == 3
    assert len(seed["feedback_ids"]) == 3
    assert seed["shortlist"][0]["overall_score"] >= seed["shortlist"][-1]["overall_score"]
    assert seed["shortlist"][0]["task_count"] == 1

    status_payload = (await client.get("/api/v1/mvp/status")).json()
    assert status_payload["counts"]["hiring_needs"] == 1
    assert status_payload["counts"]["prototype_feedback"] == 3

    reset_response = await client.post("/api/v1/demo/reset")
    assert reset_response.status_code == 204
    reset_status = (await client.get("/api/v1/mvp/status")).json()
    assert reset_status["counts"]["users"] == 0
    assert reset_status["counts"]["tasks"] == 0


async def test_trial_task_reconciliation_flags_repetition(client: httpx.AsyncClient):
    seed = (await client.post("/api/v1/demo/seed")).json()
    response = await client.post(
        "/api/v1/trial-task-reconcile",
        json={
            "hiring_need_id": seed["hiring_need_id"],
            "trial_task_text": (
                "Write another WhatsApp response to an angry refund customer, explain the policy, "
                "escalate to a supervisor and give a next step."
            ),
        },
    )

    assert response.status_code == 201
    review = response.json()
    assert review["overlap_score"] >= 45
    assert review["recommendation"] in {"Adjust", "Replace"}
    assert "Escalation judgement" in review["repeated_competencies"]


async def test_full_mvp_loop_creates_evidence_shortlist_and_feedback(client: httpx.AsyncClient):
    employer_id = await _create_employer(client)
    candidate_id = await _create_candidate(client)
    hiring_need = await _create_hiring_need(client, employer_id)

    assert "delayed deliveries" in hiring_need["role_problem_summary"].lower()
    assert len(hiring_need["skill_map"]) >= 6
    assert len(hiring_need["tasks"]) == 3
    assert hiring_need["criteria"]["overall_benchmark"] == 70

    tasks_response = await client.get(f"/api/v1/hiring-needs/{hiring_need['id']}/tasks")
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()
    assert [task["title"] for task in tasks] == [
        "Task A: Delayed delivery complaint",
        "Task B: Refund escalation response",
        "Task C: Support ticket summary",
    ]

    submission_response = await client.post(
        "/api/v1/submissions",
        json={
            "candidate_id": candidate_id,
            "hiring_need_id": hiring_need["id"],
            "task_id": tasks[0]["id"],
            "answer": (
                "Hi Sarah, I am sorry your order has taken this long. I understand how frustrating "
                "it is after paying five days ago. I will check the delivery status with dispatch "
                "now and update you before 4pm today. If it cannot move today, I will escalate it "
                "to operations for the refund option under our policy."
            ),
        },
    )

    assert submission_response.status_code == 201
    submission_payload = submission_response.json()
    evaluation = submission_payload["evaluation"]["parsed_json"]
    assert set(evaluation) >= {
        "overall_score",
        "skill_score",
        "evidence_score",
        "readiness_score",
        "role_fit_score",
        "growth_score",
        "confidence_band",
        "confidence_reason",
        "recommended_action",
        "rubric_breakdown",
        "evidence_quotes",
        "strengths",
        "gaps",
        "improvement_plan",
        "human_review_required",
        "ethics_note",
    }
    assert evaluation["overall_score"] >= 70
    assert evaluation["confidence_band"] in {"Medium", "High"}
    assert "submitted work evidence" in evaluation["ethics_note"]
    assert submission_payload["passport"]["public_summary"]["overall_score"] == evaluation["overall_score"]
    assert submission_payload["improvement_route"]["retry_allowed"] is True

    shortlist_response = await client.get(f"/api/v1/hiring-needs/{hiring_need['id']}/shortlist")
    assert shortlist_response.status_code == 200
    shortlist = shortlist_response.json()
    assert len(shortlist) == 1
    assert shortlist[0]["candidate_id"] == candidate_id
    assert shortlist[0]["task_count"] == 1

    action_response = await client.post(
        "/api/v1/employer-actions",
        json={
            "employer_id": employer_id,
            "candidate_id": candidate_id,
            "hiring_need_id": hiring_need["id"],
            "action": "trial_task",
            "note": "Good first signal. Ask for refund escalation task next.",
        },
    )
    assert action_response.status_code == 201
    assert action_response.json()["action"] == "trial_task"

    feedback_response = await client.post(
        "/api/v1/prototype-feedback",
        json={
            "tester_type": "trainer",
            "observations": "The skill gaps are useful for coaching.",
            "doubts": "Need to know when AI confidence is low.",
            "trust_signals": "Rubric and ethics note are visible.",
            "changes_made": "Added confidence band and human review reminder.",
        },
    )
    assert feedback_response.status_code == 201

    feedback_list = (await client.get("/api/v1/prototype-feedback")).json()
    assert len(feedback_list) == 1
    assert feedback_list[0]["tester_type"] == "trainer"


async def test_below_benchmark_submission_gets_improvement_route(client: httpx.AsyncClient):
    employer_id = await _create_employer(client)
    candidate_id = await _create_candidate(client, name="Weak Signal Candidate", email="weak@example.com")
    hiring_need = await _create_hiring_need(client, employer_id)
    task = hiring_need["tasks"][0]

    response = await client.post(
        "/api/v1/submissions",
        json={
            "candidate_id": candidate_id,
            "hiring_need_id": hiring_need["id"],
            "task_id": task["id"],
            "answer": "We will check.",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    evaluation = payload["evaluation"]["parsed_json"]
    assert evaluation["confidence_band"] == "Low"
    assert evaluation["recommended_action"] == "Not enough evidence"
    assert evaluation["human_review_required"] is True
    assert payload["improvement_route"]["visibility"] == "improve_first"
    assert "too short" in payload["improvement_route"]["reason"].lower()


async def _create_employer(client: httpx.AsyncClient) -> int:
    response = await client.post(
        "/api/v1/employer-profiles",
        json={
            "user": {
                "full_name": "Ada Employer",
                "email": "ada@example.com",
                "role": "employer",
            },
            "company_name": "Lagos Style Market",
            "company_type": "Growing ecommerce SME",
            "sector": "Retail ecommerce",
            "support_channel": ["WhatsApp", "Email"],
            "customer_volume": "250 to 400 messages weekly",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_candidate(
    client: httpx.AsyncClient, name: str = "Amaka Okafor", email: str = "amaka@example.com"
) -> int:
    response = await client.post(
        "/api/v1/candidate-profiles",
        json={
            "user": {
                "full_name": name,
                "email": email,
                "role": "candidate",
            },
            "location": "Lagos, Nigeria",
            "experience": "Six months handling Instagram and WhatsApp customer messages.",
            "role_interest": "Entry-level customer support",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_hiring_need(client: httpx.AsyncClient, employer_id: int) -> dict:
    response = await client.post(
        "/api/v1/hiring-needs",
        json={
            "employer_id": employer_id,
            "rough_jd": "Customer support assistant for WhatsApp complaints, refunds, and ticket summaries.",
            "intake_answers": {
                "why_hiring_now": "delayed deliveries are increasing and support messages are piling up",
                "company_stage": "Growing fashion ecommerce SME in Lagos",
                "channels": ["WhatsApp", "Email"],
                "common_issues": "delayed delivery, refund pressure, wrong size, missing order updates",
                "weekly_ticket_volume": "250 to 400 messages weekly",
                "bad_hire_cost": "refund losses, angry reviews, and poor operations handoff",
                "first_30_days": "reply to WhatsApp complaints and escalate urgent refund cases",
                "tools_or_processes": "Google Sheets, WhatsApp Business, refund policy checklist",
                "priority_skills": ["Empathy", "Clarity", "Escalation judgement", "Ownership"],
            },
        },
    )
    assert response.status_code == 201
    return response.json()
