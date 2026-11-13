# Feature 1 Windows handoff

Use [PR #2](https://github.com/tejaswini143-byte/BHASHALEARN-AI/pull/2) and branch
`fix/feature1-voice-diagnostics-ci-20261113`. The PR verification section records
the exact verified head and its GitHub Actions run. The incoming verified commit
was `31973c95ca7f4f11621f441aa76c3fefa83a4a53`
([CI](https://github.com/tejaswini143-byte/BHASHALEARN-AI/actions/runs/43401384223)).
Live microphone, provider, and Windows acceptance remain pending.

## Isolated checkout and configuration

Use a disposable Windows desktop session with Python 3.13, Node.js 22, Git,
Chrome or Edge, and a microphone. From your existing checkout, inspect local
changes and create a separate worktree. Record the checked-out SHA and compare
it to the verified head in PR #2.

```powershell
git status --short --branch
git fetch origin fix/feature1-voice-diagnostics-ci-20261113
git worktree add --detach ..\BHASHALEARN-AI-feature1-acceptance FETCH_HEAD
Set-Location ..\BHASHALEARN-AI-feature1-acceptance
git rev-parse HEAD
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r scripts\requirements-desktop.txt
if (-not (Test-Path .env)) { Copy-Item backend\.env.example .env }
```

Configure the ignored root `.env` locally. Set
`BHASHALEARN_DATABASE_URL=sqlite:///./feature1-acceptance.sqlite3` to a fresh
file, `BHASHALEARN_JWT_SECRET_KEY` to a fresh random value, and set
`GNANI_API_KEY`, `BHASHALEARN_GEMINI_API_KEY`, and
`BHASHALEARN_GEMINI_MODEL` for the authorized test account. Ensure process
environment overrides point at the same disposable setup. Create a fresh
student at `http://127.0.0.1:5173/register` in a dedicated browser profile.
Retire the previously exposed disposable account credential through the account
owner's normal rotation process.

## Mocked checks before live startup

From the worktree root:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q backend\tests
Push-Location frontend
npm ci
npm test
npm run build
npx playwright install chromium
$env:BHASHALEARN_E2E_START_SERVERS = '1'
$env:BHASHALEARN_E2E_MOCK_API = '1'
npm run test:e2e -- gnani-voice-classroom.spec.ts
Remove-Item Env:BHASHALEARN_E2E_START_SERVERS, Env:BHASHALEARN_E2E_MOCK_API
Pop-Location
```

## Startup and health checks

Run each block in a separate PowerShell window from the worktree root.

```powershell
& .\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8027
```

```powershell
Set-Location frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

```powershell
& .\scripts\start_desktop_companion.ps1
```

Verify the API, database, frontend proxy, and companion listener from another
window. Pair through the app when ready and confirm control starts disabled.

```powershell
Invoke-RestMethod http://127.0.0.1:8027/health
Invoke-RestMethod http://127.0.0.1:8027/ready
Invoke-RestMethod http://127.0.0.1:5173/health
Test-NetConnection 127.0.0.1 -Port 18765 -InformationLevel Quiet
```

## Live acceptance and evidence

Follow the [local acceptance checklist](FEATURE1-LOCAL-ACCEPTANCE.md).
Ask separately before each physical capture, live provider request, or Windows
action. Start with one English “Open Notepad” capture, listen to the local
preview, and continue only if Prisma returns the intended command and Gemini
proposes just opening Notepad. Verify both confirmations, an independently
observed new disposable Notepad window, and Emergency Stop. Continue with
the other checklist cases only after this succeeds.

Record the tested SHA, case and language, capture diagnostics, synthetic test
phrase and transcript, reviewed plan, confirmation outcomes, independently
observed result, Stop result, and any failed stage. Keep keys, tokens, raw audio,
private text, and unredacted traces local. If a stage fails, save its safe
diagnostics and stop before any downstream action.

At shutdown, click **Emergency Stop**, discard pending local audio, and press
Ctrl+C in each of the three test service windows. Leave PR #2 draft until the
required live cases pass. Push only verified Feature 1 changes as a fast-forward
to the existing feature branch and update the PR with the exact evidence.
