# BE-10 — Backend Integration and Validation

## Automated integration tests

Run from the repository root:

```cmd
python -m pytest -q backend\tests
```

Three new tests exercise registration, login, student preferences, session creation, mocked AI tutor chat, memory creation, progress updates, cross-student isolation and invalid JWT rejection. They use isolated SQLite databases and do **not** contact Gemini or PostgreSQL.

## PostgreSQL migration check

With the configured PostgreSQL connection, run:

```cmd
python -m alembic -c backend\alembic.ini current
```

Expected head: `0004_learning_memories`. Never share your database password.

## Live Gemini smoke test (manual, not covered by tests)

1. Set `BHASHALEARN_GEMINI_API_KEY` in the local environment. Do not paste the key into chat or commit it.
2. Start `python -m uvicorn backend.app.main:app --reload` from repository root.
3. Use authenticated registration/login to obtain a bearer token, create a session, then call `POST /api/v1/tutor/sessions/{session_id}/chat` with `{"message":"Explain hello in Telugu and English"}`.
4. Confirm the response contains a teaching reply and `GET /api/v1/sessions/{session_id}/messages` contains both messages.

## Findings and remaining work

- Existing session, memory and progress endpoints enforce student ownership; the integration tests cover cross-module access.
- **Known security gap:** BE-06 `POST /sessions/{session_id}/messages` permits authenticated students to submit `assistant` messages. This must be restricted before production.
- **Known trust gap:** mastery scores and attempts can be supplied by students; move score calculation to trusted assessments.
- **AI validation gap:** tests mock Gemini; live provider access and bilingual output are not yet verified.
- No automated PostgreSQL integration, rate limiting, streaming, concurrency, or load tests in this task.
- No database schema change is required for BE-10.
