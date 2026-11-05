# BHASHALEARN AI Backend

FastAPI backend for authenticated student learning, PostgreSQL-backed sessions,
progress, and bilingual Gemini tutoring.

## Windows CMD setup

From the repository root:

```cmd
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m pytest -q backend\tests
python -m uvicorn backend.app.main:app --reload
```

Visit http://127.0.0.1:8000/docs for the API documentation and
http://127.0.0.1:8000/api/v1/health for the health endpoint.

Expected health response:

```json
{"status":"ok","service":"bhashalearn-api"}
```

## Configuration

Copy `backend/.env.example` to the repository root `.env`, or set
`BHASHALEARN_*` environment variables. The application reads the current
working directory's `.env` file by default. Never commit secrets.

Before starting the API, verify local PostgreSQL connectivity and migration
readiness without changing the database:

```cmd
python -m backend.scripts.db_preflight
```

The preflight reports the configured local target, authentication status,
current Alembic revision, and required application tables. It never prints the
database URL or credentials. If the revision is behind, confirm the target is
your local development database before applying migrations with:

```cmd
python -m alembic -c backend/alembic.ini upgrade head
```

## Gemini tutoring

The authenticated classroom uses the existing endpoint
`POST /api/v1/tutor/sessions/{session_id}/chat`. Set these variables in the
repository-root `.env` for live Gemini responses:

| Variable | Purpose | Default |
| --- | --- | --- |
| `BHASHALEARN_GEMINI_API_KEY` | Server-side Gemini API credential | Required for live tutoring |
| `BHASHALEARN_GEMINI_MODEL` | Gemini `generateContent` model ID | `gemini-2.5-flash` |

Placeholders are in `backend/.env.example`. Keep the key in the backend
environment; never put it in frontend `VITE_*` variables, print it, or commit
the root `.env`. The backend sends the credential in the provider request
header. With no key configured, the chat endpoint returns HTTP 503. Provider
failures, timeouts, and invalid responses return a generic HTTP 502. A failed
provider request does not save either half of the attempted chat turn.

Unit and integration tests mock the provider and do not make live Gemini calls.

## Test scope

Backend tests use isolated SQLite databases and mocked external providers. They
do not require live Gemini credentials or network access.
