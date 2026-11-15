# Feature 2 — Deadline reminders and voice

This branch is a standalone Feature 2 package based on the incomplete `origin/main` application baseline. Its API, database, and demo authentication are separate from BHASHALEARN production login. Do not merge it directly into the product app until following the integration mapping below is applied against the current application architecture.

## Local setup

Use Python 3.13 or later, PostgreSQL, and Node.js. Create an isolated Python environment in `backend/.venv`, install `backend/requirements.txt`, copy `backend/.env.example` to `backend/.env`, and set a dedicated PostgreSQL database, a long random `JWT_SECRET`, and provider credentials. Apply migrations from `backend` with `alembic upgrade head`. Run the API on port 8001 and the Vite frontend on port 5174. Never reuse the Feature 1 database or its running services.

The current Windows validation environment has Python 3.13.17 in an isolated environment, but no accessible PostgreSQL service or running Docker daemon. Backend tests use disposable SQLite databases; migration reversibility was validated on an isolated SQLite file. This is not PostgreSQL migration evidence.

## Implemented paths

- Demo register/login issues short-lived bearer tokens for the isolated `students` table. The frontend labels this as demo authentication and does not claim production login integration.
- Deadline create/edit/cancel, assignment/exam types, timezone-aware due times, reminder preferences, history, acknowledgment, completion, snooze, and rescheduling are backed by authenticated API routes.
- A durable database poller claims reminders transactionally with `SKIP LOCKED` on PostgreSQL, records events, retries transient failures with bounded exponential backoff, and recovers stale claims after process restarts. Browser delivery is persisted as a durable event for the authenticated dashboard; the dashboard polls and announces due items. This is at-least-once delivery with client-side reminder-ID speech de-duplication.
- Each deadline selects browser or phone delivery. Phone delivery jobs invoke the guarded SIP service only after rechecking consent, verified number, test allowlist, quiet hours, rate limits, and service configuration; otherwise they retry with the same bounded policy. Browser is the default.
- Browser sessions can request a short-lived participant token and agent dispatch. The LiveKit worker uses a Google Gemini LLM plugin, Gnani Prisma REST STT through LiveKit's non-streaming STT interface plus VAD turn segmentation, and Gnani Timbre REST TTS through LiveKit's non-streaming TTS interface. It understands English and Telugu intents and persists tool actions only against the session owner's reminder.
- The browser voice client has explicit microphone start/stop and server-side session cleanup. A text and browser speech fallback is available when LiveKit configuration is absent.
- Outbound telephony is disabled by default. An explicit authenticated dispatch endpoint can create a LiveKit room, dispatch the agent, and create a SIP participant only after checking calling hours, per-student rate limits, explicit active consent, a stored verified phone, the `VERIFIED_TEST_NUMBERS` allowlist, approved caller ID, trunk, and `ALLOW_TEST_CALLS=true`. It has idempotent call records, a history endpoint, and signed LiveKit webhook reconciliation for ringing/answered/ended/no-answer. Mocked SIP dispatch tests pass. This branch does not implement OTP delivery/phone verification, and LiveKit webhooks do not establish a live carrier outcome in this environment. No calls have been placed; live SIP remains blocked.

## Environment-specific validation

Backend: `backend/.venv/Scripts/python.exe -m pytest -q` from the repository root. Alembic: set `DATABASE_URL` to an isolated disposable database and run `alembic upgrade head`, `alembic downgrade base`, then `alembic upgrade head` from `backend`. Frontend: `npm test` and `npm run build` from `frontend`.

## Integration mapping for the current product app

Feature 1's current application architecture was inspected read-only from its separate acceptance worktree. That code must remain untouched while integrating this branch.

| Feature 2 standalone piece | Product integration target | Required change |
| --- | --- | --- |
| `Student` and `/api/auth/*` demo auth | Existing `Student` model and `current_student` dependency in `backend/app/api/auth.py` | Remove demo register/login; use the host JWT/password dependency and map the authenticated product student's string UUID to reminder ownership. |
| `backend/app/models.py` and migrations `0001`, `0002` | Product SQLAlchemy models/migrations and existing assistant deadline/job records | Reconcile with product `assistant_deadlines`, `assistant_jobs`, and local-call history; do not create duplicate deadline tables. Generate a reviewed migration against the product's real head revision. |
| `/api/*` routes in `backend/app/api.py` and `voice_api.py` | Product `/api/v1/assistant/*` router layout | Mount under the existing versioned assistant router, apply `current_student`, and preserve existing ownership/role checks. |
| Standalone `frontend/src/main.tsx` and `LiveKitReminder.tsx` | Existing authenticated React/Vite dashboard and `DeadlineCallAssistant.tsx` | Port components/styles into the product shell; replace local demo token lookup with the host auth client and reuse existing design components. |
| `livekit_adapters.py` and existing Gnani POCs | Existing product provider adapter/configuration modules | Consolidate credentials/config and reuse the product's adapter lifecycle; retain explicit turn-based/non-streaming capabilities until providers offer verified streaming APIs. |
| `settings.py` environment names | Product `BHASHALEARN_` settings convention | Map database, Gemini, Gnani, LiveKit, and SIP keys to central settings/secrets; never expose service keys to Vite. |
| Scheduler lifespan in `main.py` | Existing product worker/scheduler process | Run as a dedicated worker or integrate into the product durable job runner; keep DB locking, outbox events, retries, and uniqueness constraints. |

Do not merge this isolated foundation as-is. First port the feature into the current product auth, schema, migration head, API version, frontend shell, and worker lifecycle; then run cross-branch migration and end-to-end tests in a dedicated integration environment.
