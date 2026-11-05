# BE-05 — Courses and Lessons API

## Endpoints
- `GET /api/v1/courses` — public catalog, optional `language`, `limit`, `offset`
- `POST /api/v1/courses` — create a course (JWT required)
- `GET /api/v1/courses/{course_id}` — course details
- `GET /api/v1/courses/{course_id}/lessons` — lessons in ascending position order
- `POST /api/v1/courses/{course_id}/lessons` — create a lesson (JWT required)
- `GET /api/v1/courses/{course_id}/lessons/{lesson_id}` — lesson details

**Security limitation:** This is a development/demo catalog. Any authenticated student can create courses and lessons. Introduce an instructor/admin role and authorization before production or exposing write endpoints publicly.

## Windows CMD

```cmd
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/bhashalearn"
python -m alembic -c backend\alembic.ini upgrade head
python -m alembic -c backend\alembic.ini current
python -m pytest -q backend\tests
```

Migration `0003_lessons` creates a new `lessons` table without dropping existing data.
