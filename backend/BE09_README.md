# BE-09 — Learning Progress Tracking

Authenticated student-owned endpoints:

- `PUT /api/v1/progress` — create or replace a topic's progress
- `GET /api/v1/progress` — list own progress, with `limit` and `offset`
- `GET /api/v1/progress/{topic}` — retrieve progress for one topic

Example PUT body:

```json
{"topic":"Greetings","mastery_score":75,"attempts":3}
```

Mastery score is between 0 and 100; attempts is nonnegative. Updating an existing topic preserves its ID. No new database migration is required.

**Development limitation:** The student may submit their own score and attempts. Production scores should be computed from trusted assessment/quiz events rather than client-provided values.

Run from project root:

```cmd
python -m pytest -q backend\tests
```
