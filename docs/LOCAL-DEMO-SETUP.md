# Local integration demo

This runbook starts the integration release candidate on loopback using its isolated SQLite preview database. It is for local QA only; it is not a production deployment recipe.

## Current verified endpoints

- Frontend: <http://127.0.0.1:15199>
- Backend health: <http://127.0.0.1:18027/health>
- Backend readiness: <http://127.0.0.1:18027/ready>
- Preview database: `.test-tmp/integration-preview-20261109-01/preview.sqlite`

The frontend proxies `/api` and `/health` to the backend. Bind both processes to `127.0.0.1`; do not expose this demo to a network.

## Start the backend

Use a PowerShell terminal in the RC root. Start this only when port 18027 is free; do not start a second backend over the already-running one.

```powershell
Set-Location 'C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109'
$env:BHASHALEARN_DATABASE_URL = 'sqlite:///C:/Users/Tejaswini/BHASHALEARN-INT26/_integration_rc_20261109/.test-tmp/integration-preview-20261109-01/preview.sqlite'
$env:BHASHALEARN_PORT = '18027'
& 'C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe' scripts/run_rc_backend.py --host 127.0.0.1 --port 18027
```

`scripts/run_rc_backend.py` reads only the allowlisted Gemini/Gnani provider settings from the parent project’s local `.env`; it does not print their values. Keep that file private. The script creates a process-only JWT secret if none is set, so restarting the backend invalidates existing login tokens. Students can sign in again; the SQLite rows remain.

## Start the frontend

Use a second PowerShell terminal. Start this only when port 15199 is free.

```powershell
Set-Location 'C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109\frontend'
$env:BHASHALEARN_API_PROXY_TARGET = 'http://127.0.0.1:18027'
npm.cmd run dev -- --host 127.0.0.1 --port 15199
```

Open <http://127.0.0.1:15199>. For smoke checks, `/health` and `/ready` on port 18027 should return HTTP 200, with readiness reporting the database as `ok`.

## Local quality checks

```powershell
Set-Location 'C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109\frontend'
npm.cmd test
npm.cmd run build
Set-Location '..'
& 'C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe' -m pytest backend/tests
```

The current baseline on 2026-11-11 is 82 frontend tests passed; 252 backend tests passed and 3 skipped; TypeScript and Vite build passed. The build reports a large Three.js vendor chunk.

## Acceptance boundaries

- Gemini tutoring, generated quizzes, document embeddings, and grounded PDF answers were verified with real provider responses.
- Gnani Prisma speech transcription and Timbre speech output were verified in the local student flow. A complete interruption while teacher audio is already playing, followed by resumed playback, still needs a dedicated browser test.
- Course enrollment/progress, quiz history, and learning memory persist in the isolated SQLite database. Career planning is a deterministic local roadmap, not a live job forecast.
- No rights-cleared rigged full-body teacher asset is present. A photo preview is not a realistic animated avatar or accurate lip sync.
- Gmail/Calendar OAuth, live calling, job application automation, HoloOS, and Windows desktop control are not deployment-ready. No email, call, payment, or job application was sent.
- A synthetic PDF used for RAG is still in the isolated preview account because the browser Delete interaction timed out; the document and index were preserved rather than removed directly from the database.
- Apply and test database migrations against the target deployment database, review auth/token/approval controls, and obtain a licensed teacher asset before deployment. Do not use the test database or process-only JWT secret in production.
