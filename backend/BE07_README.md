# BE-07 — AI Teaching Orchestration

`POST /api/v1/tutor/sessions/{session_id}/chat` (JWT required) accepts `{"message":"Hello"}` and returns the Gemini teaching reply.

The endpoint checks session ownership, uses the student's preferred language, learning level and learning goal, includes up to 19 recent saved messages, calls Gemini, then persists the user/assistant message pair. Provider failures return 502 and do not save partial exchanges.

## Configuration

In Windows CMD, set `BHASHALEARN_GEMINI_API_KEY` to your Gemini API key (never commit or share it). Optionally set `BHASHALEARN_GEMINI_MODEL` (default `gemini-2.5-flash`). This key is separate from the Gnani API key.

## Tests

```cmd
python -m pytest -q backend\tests
```

Tests mock the provider; live Gemini calls are not verified by automated tests. No database migration is required.

**Security and scope:** This is an initial backend integration. Assistant messages can still be submitted via the BE-06 development endpoint; protect that route before production. This endpoint is synchronous and has no retry, rate limiting, or streaming. API keys remain server-side.
