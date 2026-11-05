# FE-03 — Authentication UI

## Routes
- `/register`: create student with email, display name and password (12–128 characters); signs in after successful registration.
- `/login`: authenticate existing student.
- `/dashboard`: protected temporary welcome page; verifies token with `GET /api/v1/auth/me` and provides sign out.

## API
Uses Vite's existing `/api` proxy to the FastAPI server at `http://127.0.0.1:8000`. Start both servers.

## Test on Windows
Terminal 1 (repository root):
```cmd
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --reload
```
Terminal 2:
```cmd
cd frontend
npm install
npm run build
npm run dev
```
Visit http://localhost:5173/register. Register with a unique test email and password at least 12 characters, confirm redirect to /dashboard, sign out, sign in again, and try wrong credentials. Try opening /dashboard after signing out to confirm redirect to /login.

## Important
- This development implementation stores the JWT in browser `sessionStorage`, which is vulnerable to token theft if script injection occurs. For production, consider secure, HttpOnly, SameSite cookies with appropriate CSRF protections.
- There is no password reset, email verification, refresh token or rate limiting yet.
- The dashboard is a placeholder; FE-04 will implement it.
- Never expose API keys or tokens in browser code or screenshots.
