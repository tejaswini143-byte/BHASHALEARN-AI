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

## Gnani voice classroom (INT-03)

The authenticated voice endpoints are:

- `POST /api/v1/voice/sessions/{session_id}/transcribe` — multipart fields
  `audio` (PCM WAV) and `language` (`english`, `telugu`, or `mixed`). It returns
  the raw Prisma transcript and detected-language metadata without saving a
  message. The transcript is submitted separately through the existing Gemini
  chat endpoint so a voice turn is persisted exactly once.
- `POST /api/v1/voice/sessions/{session_id}/speech` — JSON `text` (1–3000
  characters) and optional `language` (`english`, `telugu`, or `mixed`). It
  returns playable `audio/wav` and does not create or modify chat messages.

Both routes require a bearer token and verify that the session belongs to the
authenticated student. They reuse the POC-01 Prisma and POC-02 Timbre clients.
`GNANI_API_KEY` is server-only and is read from the process environment first,
then the existing POC-01/02/03/06 local `.env` files. The remaining optional
provider settings and safe placeholders are listed in `backend/.env.example`.
Never expose these values to Vite or the browser. Use PCM `.wav` input up to
10 MiB and 30 seconds; the browser voice studio converts microphone input to
16 kHz mono PCM WAV for Prisma.
Prisma's existing configuration uses the POC-01 `language_code` setting
(default `indic-auto`) and `format=codemix`; the browser language mode informs
the tutor and does not claim a separate provider recognition model. Timbre uses
the existing English (`en-IN`/Kaveri) and Telugu (`te-IN`/Suhana) mappings. A
mixed response uses POC-06's deterministic script segmentation and joins the
returned PCM WAV frames; voice quality at language boundaries should be checked
by a listener.

Run voice tests with `python -m pytest -q backend\tests\test_voice.py`. The
normal full backend command remains `python -m pytest -q backend\tests`. Start
the API and frontend using the commands above, then visit `/voice`, select a
language, record and stop, review/correct the transcript, and send it to the
tutor. **Listen / replay** requests speech for already persisted assistant
text only; it never resends the student turn to Gemini. Browser playback can be
blocked by autoplay policy; use the audio player's Play control in that case.

## Test scope

Backend tests use isolated SQLite databases and mocked external providers. They
do not require live Gemini credentials or network access.
