# Feature 2 — Deadline Reminders

The feature package is isolated under `backend/` and `frontend/`. Use a separate Python environment and PostgreSQL database; the default development ports are API `8001` and Vite `5174`.

## Current baseline and integration boundary

This branch is based on `origin/main` at `039bdfb`, whose repository contains only the Prisma and Timbre POCs. It has no product backend, login implementation, Prisma schema, React app, or existing design-system components. Consequently this feature package does not claim to be merged into the app shell. The API requires the host app to issue an HS256 bearer token with a UUID `sub` for a row in `students`; replace the isolated `Student` mapping and token secret with the host application's auth dependency/schema before deployment. Never use the development JWT secret in production.

## Local setup

1. Copy `backend/.env.example` to `backend/.env`, set a private long JWT secret and a dedicated PostgreSQL database on port 55432.
2. Create a Python virtual environment in `backend/.venv`, install `backend/requirements.txt`, then run migrations from `backend` with `alembic -c alembic.ini upgrade head`.
3. Run the API with `uvicorn app.main:app --app-dir backend --port 8001` from the repository root.
4. Set `VITE_API_URL=http://127.0.0.1:8001/api` in `frontend/.env.local`, install the frontend lockfile/dependencies, and run Vite on port 5174. The app reads `accessToken` from localStorage; the host login should supply it.

PostgreSQL stores deadlines, student preferences, durable scheduled jobs, and event history. The worker claims due rows using `FOR UPDATE SKIP LOCKED`, so multiple workers avoid duplicate claims. Due browser reminders become visible as `in_progress` and the UI polls every ten seconds. A process restart recovers timed-out sessions and applies a bounded retry count.

## Provider status

- Prisma v3 and Timbre v2.5 are currently REST/file adapters in `pocs/`; they do not provide a validated real-time LiveKit audio interface. The POC adapters are reused by no streaming claim in this branch.
- Gemini is used for text transcript intent interpretation when `GEMINI_API_KEY` is configured. Deterministic fallback intents support basic English/Telugu acknowledgments, completion, and a 30-minute snooze.
- Browser speech capture and playback use browser Web Speech APIs. This is a browser conversation path, not a LiveKit Agents session, and support depends on the browser.
- Outbound SIP is gated by student consent, verified phone, trunk, approved caller ID and `ALLOW_TEST_CALLS`. A number verification flow and actual dialing are not yet implemented. No phone calls are placed.

## Known integration blockers

- Replace the isolated student model/token expectation with the real BHASHALEARN login, database schema, and dashboard shell when that code is available in this worktree.
- Implement and validate a LiveKit Agents worker and Gnani request/response adapters for its media interfaces; both Gnani providers exposed here are REST, not streaming.
- Add phone verification, a verified test-number allowlist, SIP dispatch plus webhook status reconciliation, and authorized test-call evidence before enabling dialing.
- Configure the product voice preference endpoint and wire controls to persist language, voice, consent, and verified phone settings.
