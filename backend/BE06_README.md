# BE-06 — Learning session management

Authenticated, student-owned endpoints:

- `POST /api/v1/sessions` — create a learning session (`topic`, `language`, optional `course_id`)
- `GET /api/v1/sessions` — list own sessions (`limit`, `offset`)
- `GET /api/v1/sessions/{session_id}` — get own session
- `POST /api/v1/sessions/{session_id}/messages` — save a user or assistant message
- `GET /api/v1/sessions/{session_id}/messages` — read own history (`limit`, `offset`)

JWT bearer token required for all endpoints. Foreign sessions return 404 rather than exposing their existence. Messages are returned by timestamp, then ID, ascending. For future deterministic sequence ordering under high concurrency, add a per-session sequence column.

**Development-only limitation:** The client may submit assistant messages. In production, assistant messages should be created only by the trusted AI orchestration backend.

Uses the existing `learning_sessions` and `chat_messages` tables. No new migration.

Windows CMD from project root:

```cmd
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/bhashalearn"
python -m pytest -q backend\tests
```
