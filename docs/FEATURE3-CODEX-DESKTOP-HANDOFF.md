# Feature 3 — Future Seeker local handoff

## Isolated source and base

- Branch: `feature/feature3-future-seeker`
- Integration base: `integration/release-candidate-20261109` at `17eeee5a3bf3ab319479d0dc777d0743f6d2340a`
- The base is the release-candidate integration branch, not the unmerged Feature 1 branch. This work uses its own checkout, Python environment, browser context, and SQLite file.
- Update the tested head SHA in this section when publishing the handoff.

## Requirements

- Windows 10/11, Python 3.12, Node.js 22, npm, and Git.
- Keep this checkout's `.venv`, `frontend/node_modules`, `.env`, SQLite file, and browser test profile local to Feature 3.
- Bind development services to loopback only. Backend port `8033`; frontend port `5183`.

## Install dependencies

From the Feature 3 repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location frontend
npm ci
Set-Location ..
```

If `ensurepip` cannot write its temporary files, create a temporary directory inside this checkout and set `$env:TEMP` and `$env:TMP` to it for the venv setup command. Remove only that Feature 3 temporary directory after the command has finished.

### Windows application-control note

On the current Windows policy, importing the pip-installed Argon2 `_ffi` extension failed with “An Application Control policy has blocked this file.” In the Feature 3-only environment, SQLAlchemy's optional `_result_cy` extension was also denied. Do not disable Defender, WDAC, AppLocker, Smart App Control, or another protection; do not replace Argon2 or alter password-hash compatibility. If either import is denied, stop local backend startup and use a Python/dependency installation that the device administrator has approved, or ask the administrator to approve the signed/trusted package or interpreter. Backend and migration checks also run in the isolated GitHub Actions workflow.

## Local environment and database

Copy `backend/.env.example` to the repository root `.env`, then keep it ignored. Use a new random development JWT secret and the Feature 3-only SQLite database. Never copy a Feature 1 `.env`, database, or test account into this checkout.

In the same PowerShell window used to start the backend:

```powershell
$env:BHASHALEARN_DATABASE_URL = 'sqlite:///./feature3-future-seeker.sqlite3'
$env:BHASHALEARN_JWT_SECRET_KEY = '<new-random-local-secret-at-least-32-characters>'
$env:BHASHALEARN_GEMINI_API_KEY = ''
```

Keep provider keys server-side. For the default deterministic roadmap, Gemini is optional. The “Analyze skill gaps with Gemini” button is an explicit provider request; configure a valid key only when you intend to use it. Do not put provider keys in `VITE_*` settings or commit them.

## Migrate and start the backend

From the repository root:

```powershell
\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8033
```

Verify `http://127.0.0.1:8033/health` and `http://127.0.0.1:8033/ready` both return HTTP 200; readiness should report `database: ok`.

## Start the frontend

In a second PowerShell window:

```powershell
Set-Location frontend
$env:BHASHALEARN_API_PROXY_TARGET = 'http://127.0.0.1:8033'
npm.cmd run dev -- --host 127.0.0.1 --port 5183 --strictPort
```

Open `http://127.0.0.1:5183/register`, create a new disposable Feature 3 student account, sign in, then open `http://127.0.0.1:5183/career` (Future Seeker). Do not reuse a Feature 1 test account.

## Acceptance flow

1. Create a disposable student account through the normal registration page.
2. Choose a career, enter education/field of study, self-reported skills, interests, time availability, preferred format/language, target timeframe, and constraints.
3. Generate the deterministic roadmap and verify the skill-gap labels distinguish self-reported skills from server-recorded assessment evidence.
4. Check that daily sessions do not exceed the entered study-day availability, and that recommended resources link to the curated catalog.
5. Open a catalog lesson or supported objective quiz, complete a milestone, and log study time. Confirm progress remains after sign-out and sign-in.
6. Replan and inspect Roadmap history. Confirm an earlier version and completed milestone records remain available.
7. Use “Analyze skill gaps with Gemini” only when intentionally testing a real provider request. The response must validate against the structured schema; it cannot grant verified mastery or employment claims.
8. Repeat selected profile and interface checks in English, Telugu, and mixed language.

## Automated checks

```powershell
\.venv\Scripts\python.exe -m pytest -q backend\tests
Set-Location frontend
npm.cmd test
$env:BHASHALEARN_E2E_START_SERVERS = '1'
$env:BHASHALEARN_E2E_MOCK_API = '1'
$env:BHASHALEARN_E2E_BACKEND_PORT = '8033'
$env:BHASHALEARN_E2E_FRONTEND_PORT = '5183'
npx playwright install chromium
npm.cmd run test:e2e -- e2e\career-roadmap.spec.ts
npm.cmd run build
```

The career browser test stubs the API and Gemini response; it must never send a provider request. GitHub Actions also runs backend/migration and Feature 2 regression tests, Windows companion contracts, the mocked Chromium career flow, frontend tests, and a production build.

## Troubleshooting

- `Application Control policy has blocked this file`: stop. Request an approved signed/trusted Python package or interpreter from the device administrator. Do not move the native extension into another environment or weaken security.
- `/health` works but `/ready` fails: verify the Feature 3 process has `BHASHALEARN_DATABASE_URL=sqlite:///./feature3-future-seeker.sqlite3` and that Alembic upgrade completed from the repository root.
- Frontend API calls fail: confirm Vite uses `BHASHALEARN_API_PROXY_TARGET=http://127.0.0.1:8033` and both services are bound to loopback.
- Port `8033` or `5183` is occupied: inspect its owner and choose another free Feature 3-only port. Never stop or reuse a Feature 1 service.
- Gemini analysis is unavailable: verify the server-side key is configured and non-placeholder; ordinary tests and deterministic roadmap generation do not require a live key.

## Ready-to-paste Codex Desktop acceptance prompt

```text
Continue BHASHALEARN AI Feature 3 Future Seeker acceptance in its own checkout and branch `feature/feature3-future-seeker`. First verify the checkout path, branch, tested commit, clean/expected Git status, and the Feature 3-only SQLite database. Never enter, edit, reset, rebase, or use the Feature 1 branch, database, environment, browser profile, or running services. Use backend 8033 and frontend 5183 only after confirming they are free; bind loopback. Check the Windows application-control status before installing native Python packages. Do not disable security controls or substitute password hashing. Run all backend, migration, frontend, Windows contract, mocked Playwright, and production build checks. Create a fresh disposable student account through normal registration, then verify Future Seeker onboarding, roadmap persistence, versions, progress, English/Telugu/mixed copy, study capacity, and curated resources. Keep AI provider calls mocked unless I explicitly approve one live Gemini request; ask before that request and report the exact result. Do not record microphone audio, use desktop control, modify PR #2, or merge any PR. Update this handoff/report with actual evidence and leave the Feature 3 PR draft until all acceptance gates pass.
```
