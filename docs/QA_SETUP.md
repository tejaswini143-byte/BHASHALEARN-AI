# Acceptance QA setup

This guide runs the UI contract suite with deterministic browser API mocks and, separately, the database-backed acceptance tests against a disposable PostgreSQL database. No live Gemini or Gnani credentials are needed for the mock run.

## Frontend contract and build checks

From `frontend`:

```powershell
npm.cmd ci
npm.cmd test
npm.cmd run build
$env:BHASHALEARN_E2E_START_SERVERS = '1'
$env:BHASHALEARN_E2E_MOCK_API = '1'
$env:BHASHALEARN_E2E_FRONTEND_PORT = '6194'
npm.cmd run test:e2e -- e2e/submission-acceptance.spec.ts
```

The acceptance spec stubs `/api/v1` in Playwright. Its registration, classroom, assistant, and PDF-search fixtures are synthetic. Port 6194 is a dedicated example; choose another free port for concurrent runs. Playwright starts only Vite in mock mode. The suite does not touch a database or call external AI services.

The repository's complete browser suite includes tests that expect a reachable API, configured test-only accounts, or an isolated database. Do not treat skipped database-gated cases as passes. Use the explicit E2E guards below before running any mutation workflow.

## Database-backed browser tests

Use a PostgreSQL database created only for QA whose database name includes `test`, `e2e`, or `disposable`. Never use production or the normal development database. The Playwright config requires `BHASHALEARN_E2E_DATABASE_URL` before server startup or mutating tests, rejects the known development URL, requires opt-in for mutations, assigns dedicated backend/frontend ports, and points private-document storage at a test-only folder. Migrations are operator-run; the test runner does not migrate automatically.

Example PowerShell settings (replace values in the local shell; do not commit them):

```powershell
$env:BHASHALEARN_E2E_DATABASE_URL = 'postgresql+psycopg://<test-user>:<password>@127.0.0.1:5432/bhashalearn_e2e_test'
$env:BHASHALEARN_E2E_EMAIL = '<synthetic-student-a-email>'
$env:BHASHALEARN_E2E_PASSWORD = '<synthetic-student-a-password>'
$env:BHASHALEARN_E2E_SECOND_EMAIL = '<synthetic-student-b-email>'
$env:BHASHALEARN_E2E_SECOND_PASSWORD = '<synthetic-student-b-password>'
$env:BHASHALEARN_E2E_ALLOW_AUTHENTICATED_READS = '1'
$env:BHASHALEARN_E2E_ALLOW_MUTATIONS = '1'
$env:BHASHALEARN_E2E_START_SERVERS = '1'
$env:BHASHALEARN_E2E_BACKEND_PORT = '6212'
$env:BHASHALEARN_E2E_FRONTEND_PORT = '6194'
```

Set `BHASHALEARN_DATABASE_URL` to the same disposable URL when running migrations, and set a test-only JWT secret and `BHASHALEARN_DOCUMENT_STORAGE_DIR` under the ignored test-data folder. Verify database identity and test storage before migrating. Follow `docs/ADV-01-browser-e2e-verification.md` for the existing Windows isolation script and complete setup steps. That guide's recorded historical runs are evidence for the older candidate state; rerun on this candidate before submission sign-off.

## Provider mocks and live checks

Browser API mocks are implemented in the relevant `frontend/e2e/*.spec.ts` files and return deterministic synthetic payloads. The fake embedding server is enabled only with `BHASHALEARN_E2E_FAKE_EMBEDDINGS=1`; it is a test provider and must not be described as Gemini acceptance. Gnani calls are not made by the mock suite. Live Gemini and Gnani verification requires authorized credentials, an approved cost-bearing environment, and separately recorded evidence.

Python/backend tests require the backend dependencies in a working Python environment and use the repository's test fixtures. This task did not set up a disposable DB or claim a database-backed backend run. See the result log in `docs/GNANI_SUBMISSION_HANDOFF.md`.
