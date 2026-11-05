# FE-04 — Advanced Student Dashboard

## Implemented
- Authenticated responsive dashboard at `/dashboard` with sidebar and mobile navigation.
- Personalized greeting from `GET /api/v1/auth/me`.
- Real per-topic mastery bars, average mastery ring, and attempt totals from `GET /api/v1/progress`.
- Recent learning sessions and client-side search from `GET /api/v1/sessions`.
- Language and level from `GET /api/v1/students/me/preferences`.
- Create a real learning session with `POST /api/v1/sessions`.
- Refresh, sign out, API error and empty states.
- Voice, visual, and chat are labeled **coming next** and are not falsely represented as functional.

## Run and verify
Start FastAPI in the project root:
```cmd
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --reload
```
In a second terminal:
```cmd
cd frontend
npm install
npm run build
npm run dev
```
Open http://localhost:5173/login, sign in, and open /dashboard. Create a session, verify it appears under Recent sessions, try search, refresh, and sign out. On a new account, progress charts should show truthful empty states until progress data is recorded.

## Scope and caveats
- No sample or invented student analytics are displayed.
- Session count is from the latest 20 returned by the API, not an all-time count.
- Progress is from at most 100 topics. Mastery values are presently client-writable in the backend and should not be treated as independently verified assessment results.
- The dashboard is not yet connected to FE-05/06/07/08 classrooms.
- The browser still uses sessionStorage JWTs from FE-03; production authentication hardening is outstanding.
