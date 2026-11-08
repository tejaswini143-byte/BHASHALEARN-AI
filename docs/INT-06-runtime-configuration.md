# INT-06 Runtime Configuration and Credential Security

## Canonical configuration sources

For local backend runs, copy `backend/.env.example` to the repository-root
`.env`, or provide the same variables in the process environment. Process
environment values take precedence. Do not commit a real `.env` file.

| Provider | Runtime source | Required values |
| --- | --- | --- |
| Database | `Settings` (`BHASHALEARN_*`) | `BHASHALEARN_DATABASE_URL`; empty default intentionally fails closed |
| Authentication | `Settings` (`BHASHALEARN_*`) | `BHASHALEARN_JWT_SECRET_KEY`, at least 32 characters |
| Gemini tutor | `Settings` (`BHASHALEARN_*`) | `BHASHALEARN_GEMINI_API_KEY` |
| Gemini embeddings | `Settings` (`BHASHALEARN_*`) | `BHASHALEARN_GEMINI_EMBEDDING_API_KEY`; falls back to the tutor key |
| Gnani Prisma and Timbre | `GNANI_*` values | `GNANI_API_KEY` and the documented STT/TTS settings |

Gnani reads process environment first, then the repository-root `.env`. Existing
POC-local `.env` files are supported only as a fallback for standalone POC
compatibility. Placeholder values such as `replace_me` are ignored.

Never place provider credentials in frontend `VITE_*` variables. The frontend
uses the Vite proxy and calls backend APIs; providers are configured only on the
backend.

## Historical database credential

An early development revision in commit `10992cc` contained a loopback-only,
well-known PostgreSQL default. Current `backend/app/config.py` does not use that
value and defaults `BHASHALEARN_DATABASE_URL` to empty. The historical value is
still reachable through Git history, so treat it as exposed. Manually rotate
any local or deployed database role that still accepts that default and update
its private environment configuration. This project does not connect to or
modify an existing database, rotate credentials, or rewrite Git history.

## Safe behavior

Missing database configuration stops engine creation with a configuration
error. Missing or undersized JWT configuration returns HTTP 503 rather than
issuing a token. Gemini and Gnani clients reject missing provider credentials
before making outbound requests.
