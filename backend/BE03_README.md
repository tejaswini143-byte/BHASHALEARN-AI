# BE-03 — Student authentication

Endpoints:
- `POST /api/v1/auth/register` JSON: `{"email":"student@example.com","display_name":"Student","password":"a-unique-password-123"}`
- `POST /api/v1/auth/login` JSON: `{"email":"student@example.com","password":"a-unique-password-123"}` returns a JWT.
- `GET /api/v1/auth/me` with `Authorization: Bearer <access_token>`.

Passwords use Argon2id; JWT access tokens use HS256 and expire after 30 minutes by default. Tokens and responses never include password hashes. Login uses a generic error for invalid credentials.

## Local setup (Windows CMD)

Set a **random, unique secret with at least 32 characters** in the terminal running FastAPI:

```cmd
set "BHASHALEARN_JWT_SECRET_KEY=REPLACE_WITH_YOUR_OWN_RANDOM_32_PLUS_CHARACTER_SECRET"
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/bhashalearn"
python -m pip install -r backend\requirements.txt
python -m alembic -c backend\alembic.ini upgrade head
python -m pytest -q backend\tests
python -m uvicorn backend.app.main:app --reload
```

Do not commit secrets or real passwords to GitHub. The database URL above uses the local PostgreSQL password file (`%APPDATA%\postgresql\pgpass.conf`). The JWT secret is required for token creation and verification; missing or short secrets return HTTP 503. Use HTTPS and add rate limiting, email verification, refresh-token strategy, and secret management before production.
