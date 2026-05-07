# Sabixa Backend

FastAPI backend for the Sabixa Sprint 2 MVP.

## Run

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m uvicorn app.main:app --reload
```

OpenAPI docs:

```text
http://127.0.0.1:8000/docs
```

## Test

```bash
.venv/bin/python -m pytest
```

## Demo Helpers

```text
GET  /api/v1/mvp/status
POST /api/v1/demo/seed
POST /api/v1/demo/reset
```

Use `/api/v1/demo/seed` before frontend walkthroughs to create one employer, one hiring need, three tasks, three candidates, evaluations, passports, shortlist data, and three feedback notes.

## Vercel Deployment

Deploy `backend/` as its own Vercel project root.

- Entry point: `api/index.py`
- Config: `vercel.json`
- Required runtime: Python 3.12

The frontend should point to this deployed backend through `VITE_API_BASE_URL`.

## MVP Coverage

- Employer hiring need intake.
- AI-style role summary, skill map, and 3-task customer support assessment pack.
- Candidate task submission.
- Structured fallback evaluation.
- Candidate skill passport.
- Employer ranked shortlist.
- Improvement route for below-benchmark submissions.
- Employer actions.
- Prototype feedback log for 3-user testing.
- Ethics note and human review reminder.
