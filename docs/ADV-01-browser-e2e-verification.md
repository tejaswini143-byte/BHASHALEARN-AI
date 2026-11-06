# ADV-01 Browser E2E Verification

## Scope

The Playwright suite exercises the real Vite UI and its `/api/v1` proxy. It covers login form behavior, HTTP authentication errors versus network failures, protected-route redirects, dashboard navigation, PDF upload and extracted page text, refresh persistence, deletion, invalid-file handling, and student isolation. The authenticated and mutating tests are intentionally gated so they cannot silently operate on the normal development database or a real student account.

## Setup (Windows CMD)

From the repository root:

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-ADV01\frontend
npm.cmd install
npm.cmd install --save-dev @playwright/test
npx.cmd playwright install chromium
```

The E2E runner uses `@playwright/test` and Chromium. The Playwright report and artifacts are in `frontend\playwright-report` and `frontend\test-results`; both are git-ignored.

Create a **separate disposable PostgreSQL database** yourself. Its name must contain `test`, `e2e`, or `disposable`, and it must not be the development database. Confirm the target before migrating it. Apply the existing Alembic head to that test database explicitly; Playwright never runs migrations. Set the environment variables below only in the CMD window used for the test. Do not put credentials in source files or paste them into logs.

```cmd
set BHASHALEARN_E2E_DATABASE_URL=postgresql+psycopg://<test-user>:<test-password>@localhost:5432/bhashalearn_e2e_test
set BHASHALEARN_E2E_EMAIL=<dedicated-test-student-a-email>
set BHASHALEARN_E2E_PASSWORD=<dedicated-test-student-a-password>
set BHASHALEARN_E2E_SECOND_EMAIL=<dedicated-test-student-b-email>
set BHASHALEARN_E2E_SECOND_PASSWORD=<dedicated-test-student-b-password>
set BHASHALEARN_E2E_ALLOW_AUTHENTICATED_READS=1
set BHASHALEARN_E2E_ALLOW_MUTATIONS=1
set BHASHALEARN_E2E_START_SERVERS=1
```

Create both dedicated test students only in that disposable database, using the normal registration flow. The accounts must not be real student accounts. The runner validates that the supplied database URL names a separate test/e2e/disposable database and refuses mutating E2E tests without the explicit opt-in. Credentials are read only from the process environment and are not printed.

Optionally select the Python interpreter if the repository venv launcher is unavailable:

```cmd
set BHASHALEARN_E2E_PYTHON=C:\path\to\python.exe
```

## Services and isolation

With `BHASHALEARN_E2E_START_SERVERS=1`, Playwright starts an isolated backend on port 8012 and Vite on port 5184 (configurable with `BHASHALEARN_E2E_BACKEND_PORT` and `BHASHALEARN_E2E_FRONTEND_PORT`). Strict port binding prevents reuse of an unrelated server. The child backend receives the explicit test database URL and a `test-data` private-document directory. No schema migration is performed. The app uses the existing API routes and bearer-token login.

If services are already running, set `BHASHALEARN_E2E_FRONTEND_URL` and `BHASHALEARN_E2E_BACKEND_URL` and omit server startup. The proxy test checks both that backend's direct health response and the frontend-proxied `/health` and protected API responses. In this mode, the operator must confirm that the backend really targets the disposable database before setting the mutation opt-in. The runner cannot infer a remote server's active database from its health response.

Without dedicated credentials, the public login-form, invalid-credentials, network-failure, and unauthenticated-route tests still run. Authenticated dashboard checks skip. PDF mutation and isolation checks skip unless the disposable database and explicit account/mutation configuration are present.

## Run

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-ADV01\frontend
npm.cmd run test:e2e
npm.cmd run test:e2e:headed
npm.cmd run test:e2e:report
```

Headless execution is the default. `BHASHALEARN_E2E_HEADED=1` also selects headed mode for direct Playwright invocation. Configure a non-default frontend URL with `BHASHALEARN_E2E_FRONTEND_URL`; configure a browser executable only when necessary with `BHASHALEARN_E2E_CHROMIUM_EXECUTABLE`. Each test gets a separate browser context; workers are serialized to avoid shared account races. Failures save screenshots, and traces are configured on first retry (local retries remain zero).

## Security and cleanup

- Never use an actual student's credentials or the persistent `bhashalearn` development database.
- Never enable mutation mode until the backend has been confirmed against a disposable database.
- The runner does not create accounts, alter passwords, apply migrations, or delete pre-existing documents.
- The document test uploads uniquely named synthetic PDFs and deletes only the specific document it created. If a test fails before cleanup, remove its uniquely prefixed fixture from the disposable database/storage manually.
- Test storage and browser artifacts are ignored by Git.
- The tests do not test real user credentials; they use only explicitly supplied dedicated E2E accounts.

## Troubleshooting

- `npm install` or Chromium download fails: check npm registry access and Windows proxy/firewall policy, then rerun install in the project folder. Do not fabricate a browser pass if Chromium is absent.
- `Executable doesn't exist`: run `npx.cmd playwright install chromium`.
- E2E database guard fails: create/use a separate test database whose database name includes `test`, `e2e`, or `disposable`; do not change the guard to permit the normal development DB.
- Backend server fails: verify the selected Python executable and install the backend requirements in the environment; ensure port 8012 is free. Do not terminate another process automatically.
- Vite fails: ensure port 5184 is free. The E2E server uses strict ports and will stop rather than attach to another worktree.
- Tests show `401`: confirm the dedicated test student exists in the disposable database and credentials are correct. Do not reset a real account password.

## Initial browser run before local E2E setup (2026-11-06)

- `npm.cmd run test:e2e -- --reporter=line`: **13 discovered, 0 passed, 6 failed, 7 skipped**. The six failures were connection refusals at the default frontend (`127.0.0.1:5174`) and backend (`127.0.0.1:8002`) URLs. The seven skips were the dedicated-login, dashboard, document-mutation, encrypted-fixture, and isolation cases gated on explicit test-only credentials/configuration. The tests did launch Chromium; they failed before exercising the UI because the services were not running.
- The previous approximately 2 ms durations are consistent with Playwright's intentional `test.skip(...)` guards: those cases return before browser navigation. A skipped duration is not evidence that the browser flow passed.
- Chromium is installed for Playwright 1.64.1 under `%LOCALAPPDATA%\ms-playwright` (Chromium revision 1248 and headless shell revision 1248). The current machine's E2E run therefore had a browser available.
- Ports 8002, 8012, 5174, and 5184 were closed. The Vite proxy is configured to use `BHASHALEARN_API_PROXY_TARGET` and defaults to port 8000; no live proxy/backend health response was available to verify.
- `npm.cmd test`: **9 passed, 0 failed, 0 skipped**.
- Backend regression tests: **not run**. `.venv\Scripts\python.exe` exists as a launcher but points to a missing Python 3.12 installation (`No Python at ...Python312\python.exe`); no working project Python interpreter was available.
- No E2E database URL or dedicated student credentials were configured. PostgreSQL 18 service is present, but database creation and student registration were not attempted. No authenticated or mutating browser test ran against any database, and the existing `bhashalearn` database was not contacted.
- The frontend E2E runner is configured to start an isolated backend with the explicit test database URL and `test-data\private-documents` storage when `BHASHALEARN_E2E_START_SERVERS=1`. That isolated server mode was not enabled because a disposable database and working Python environment were unavailable.

## Authorized Windows CMD database setup

An administrator or PostgreSQL role with `CREATEROLE` and `CREATEDB` permission must provision the isolated database. These commands use PostgreSQL 18's installed client path. They do not connect to or modify the `bhashalearn` database. In CMD:

```cmd
set "PG_BIN=C:\Program Files\PostgreSQL\18\bin"
"%PG_BIN%\psql.exe" -h 127.0.0.1 -p 5432 -U <postgres-admin-role> -d postgres -W
```

At the `psql` prompt, first check that `bhashalearn_e2e_test` does not already exist. If it is absent, create a dedicated login and database; enter its password at the hidden `\password` prompt:

```sql
\l
CREATE ROLE bhashalearn_e2e LOGIN;
\password bhashalearn_e2e
CREATE DATABASE bhashalearn_e2e_test OWNER bhashalearn_e2e;
\q
```

If the role cannot create roles or databases, stop and have the PostgreSQL administrator run those statements. Do not drop or reuse an existing database. Once a working Python environment with backend dependencies is available, use a separate CMD window from the repository root. URL-encode any reserved characters in the database password and replace the placeholder locally:

```cmd
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://bhashalearn_e2e:<URL_ENCODED_PASSWORD>@127.0.0.1:5432/bhashalearn_e2e_test"
".venv\Scripts\python.exe" -m alembic -c backend\alembic.ini upgrade head
```

Start a temporary backend and Vite instance against only the test database so the two synthetic students can be registered. In the same root CMD window used for migration:

```cmd
set "BHASHALEARN_DOCUMENT_STORAGE_DIR=%CD%\test-data\private-documents"
set "BHASHALEARN_JWT_SECRET_KEY=e2e-only-local-secret-not-for-production"
".venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8012
```

In a second CMD window:

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-ADV01\frontend
set "BHASHALEARN_API_PROXY_TARGET=http://127.0.0.1:8012"
npm.cmd run dev -- --host 127.0.0.1 --port 5184 --strictPort
```

Open `http://127.0.0.1:5184/register` and register two newly created, synthetic test students. Do not use real accounts. Close both temporary services after registration. Then run the suite from a fresh CMD window so credentials stay out of source files and test output:

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-ADV01\frontend
set "BHASHALEARN_E2E_DATABASE_URL=postgresql+psycopg://bhashalearn_e2e:<URL_ENCODED_PASSWORD>@127.0.0.1:5432/bhashalearn_e2e_test"
set "BHASHALEARN_E2E_EMAIL=<test-student-a-email>"
set "BHASHALEARN_E2E_PASSWORD=<test-student-a-password>"
set "BHASHALEARN_E2E_SECOND_EMAIL=<test-student-b-email>"
set "BHASHALEARN_E2E_SECOND_PASSWORD=<test-student-b-password>"
set "BHASHALEARN_E2E_ALLOW_AUTHENTICATED_READS=1"
set "BHASHALEARN_E2E_ALLOW_MUTATIONS=1"
set "BHASHALEARN_E2E_START_SERVERS=1"
npm.cmd run test:e2e -- --reporter=line
```

The test runner uses port 8012 for the isolated API, port 5184 for Vite, and writes private test documents under the repository's ignored `test-data\private-documents` directory. Do not set `BHASHALEARN_E2E_DATABASE_URL` to the development database. The Python launcher must be repaired or `BHASHALEARN_E2E_PYTHON` must point to a working interpreter before running this command.

## Continuation results and local setup

The previous browser run remains the last E2E execution: **0 passed, 6 failed, 7 skipped**. It failed because the configured frontend/backend services were unavailable; the skip guards were not changed. The encrypted PDF fixture is now generated under ignored `test-data` so the encrypted-PDF case can run once the suite is started with local credentials.

Python 3.12.10 was used to create a separate `.venv-e2e`; the older `.venv` was preserved. Dependencies were installed from `backend\requirements.txt`. Regression results in this continuation are **96 backend tests passed**, **9 frontend tests passed**, and `npm.cmd run build` succeeded. Chromium was previously installed and launched by Playwright.

The dedicated PostgreSQL role and database are user-confirmed, but no database password was entered into this session. To save it only in the ignored `.env.e2e.local` file, run this from a local PowerShell window and enter the password at the hidden prompt. The script URL-encodes reserved characters and generates two unique synthetic student credentials without displaying them:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\Tejaswini\BHASHALEARN-ADV01\scripts\setup_adv01_e2e_local.ps1
```

Before migration, source that local file into the current PowerShell process, set the explicit backend database and test-only storage paths, and run the fail-closed identity/storage check. Continue only if it reports the expected database, role, and isolated storage:

```powershell
Get-Content .env.e2e.local | ForEach-Object { $key, $value = $_ -split '=', 2; Set-Item -Path "Env:$key" -Value $value }
$env:BHASHALEARN_DATABASE_URL = $env:BHASHALEARN_E2E_DATABASE_URL
$env:BHASHALEARN_DOCUMENT_STORAGE_DIR = Join-Path $PWD 'test-data\private-documents'
& .\.venv-e2e\Scripts\python.exe scripts\verify_adv01_e2e_isolation.py
if ($LASTEXITCODE -ne 0) { throw 'E2E identity/storage verification failed; do not migrate or run mutations.' }
& .\.venv-e2e\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

`verify_adv01_e2e_isolation.py` checks the parsed URL names role `bhashalearn_e2e` and database `bhashalearn_e2e_test`, connects and verifies `current_database()` and `current_user`, and confirms storage resolves to the ignored `test-data\private-documents` directory and does not overlap `backend\storage\documents`. It prints no credentials. Run the app's normal registration flow twice at `/register` against the E2E backend and use the generated test account values from the ignored config. Set `BHASHALEARN_E2E_ENCRYPTED_PDF` from that config to the generated ignored fixture path, then run all 13 Playwright tests with `BHASHALEARN_E2E_START_SERVERS=1`.

At the time of that continuation update, no password had yet been entered into `.env.e2e.local`; no E2E database connection, migration, student creation, or authenticated/mutating browser test had been performed. Those checks were completed in the final execution below without accessing the existing `bhashalearn` database or real student accounts.

## Final execution results (2026-11-06)

- Guarded run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts\run_adv01_e2e.ps1`.
- Playwright/Chromium: **13 passed, 0 failed, 0 skipped**. The suite covered HTTP 401 versus network failure, login/logout/session refresh, dashboard/navigation, two-page PDF upload/extraction and refresh persistence, deletion, invalid/corrupt/textless/encrypted PDFs, and student isolation.
- Database guard confirmed `current_database() = bhashalearn_e2e_test` and `current_user = bhashalearn_e2e`. Alembic migrations through `0007_private_documents` were applied only to that database.
- Storage guard confirmed the backend resolved private PDF files to this worktree's `test-data\private-documents`, separate from `backend\storage\documents`.
- Both synthetic students were registered through the `/register` UI and authenticated. Their credentials remain only in ignored `.env.e2e.local`.
- Service checks: direct FastAPI health **200**, Vite `/health` proxy **200**, and unauthenticated proxied documents API **401**.
- Backend regression suite: **96 passed**. Frontend suite: **9 passed**. Frontend production build: **passed**. `git diff --check`: **passed**.
- The initial fully configured E2E attempts exposed and fixed a reserved-domain registration fixture, an early-awaited upload response, a missing owner login in isolation setup, a missing token argument in the isolation list request, and an ambiguous page-count locator. Assertions remain enabled and none of the tests were converted to skips.
- No commands connected to or modified the existing `bhashalearn` database. No real student accounts were used. No commit or push was made.

To reproduce in this worktree, enter the DB password locally with `scripts\setup_adv01_e2e_local.ps1`, then run `scripts\run_adv01_e2e.ps1`. The runner loads ignored local settings without printing them, verifies database identity and storage before migrations and tests, applies migrations only to the named E2E database, starts strict-port isolated services, creates/verifies the two synthetic students through the UI, and runs the browser suite. It refuses to continue if ports are already occupied or the isolation guard fails.
