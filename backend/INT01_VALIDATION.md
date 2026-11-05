# INT-01 — Authentication, dashboard, and learning sessions integration

## Scope
Verify real running FastAPI endpoints against PostgreSQL:
- GET /api/v1/health
- POST /api/v1/auth/register
- POST /api/v1/auth/login
- GET /api/v1/auth/me
- GET /api/v1/students/me/preferences
- GET /api/v1/progress?limit=100
- GET /api/v1/sessions?limit=20
- POST /api/v1/sessions
- GET /api/v1/sessions/{id}/messages?limit=500
- anonymous 401 enforcement

## Windows CMD test
Terminal A, from repository root:
```cmd
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --reload
```
Terminal B:
```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
git fetch origin
git switch feature/int-01-api-verification
git pull origin feature/int-01-api-verification
python backend/scripts/int01_smoke.py
```
Run the script only against a development database. It creates one disposable student and one session and does not delete them.

## Browser verification
Start frontend with `cd frontend && npm run dev`. Open `http://localhost:5173/register` and create a student (password at least 12 characters), log in, open `/dashboard`, verify all three experience cards, create a topic, confirm it appears in recent sessions, then sign out and confirm `/dashboard` redirects to login.

## Acceptance criteria
- Smoke script prints all PASS and exits zero
- Frontend `npm run build` passes
- Registration, login, dashboard and session creation work through Vite proxy in browser
- No 401/404/500 on expected authenticated endpoints
- User confirms results before proceeding to INT-02

**Not yet verified:** Real PostgreSQL, browser workflows, live Gemini API, Gnani APIs. Script results depend on user's local environment.
