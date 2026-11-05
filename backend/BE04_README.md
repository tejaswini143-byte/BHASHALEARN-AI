# BE-04 — Student management

Authenticated endpoints (JWT bearer token required):

- `GET /api/v1/students/me` — current student's public profile.
- `PATCH /api/v1/students/me` — update display name.
- `GET /api/v1/students/me/preferences` — return persisted preferences or defaults.
- `PUT /api/v1/students/me/preferences` — replace preferred language, level, and learning goal.

Allowed languages: `telugu`, `english`, `mixed`. Levels: `beginner`, `intermediate`, `advanced`.

A new Alembic migration `0002_student_preferences` creates the preferences table; do not reset the existing database.

Windows CMD, with the virtual environment activated and PostgreSQL password file configured:

```cmd
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/bhashalearn"
python -m alembic -c backend\alembic.ini upgrade head
python -m alembic -c backend\alembic.ini current
python -m pytest -q backend\tests
```

JWT secret is still required for login/authenticated requests. Run tests from the repository root.
