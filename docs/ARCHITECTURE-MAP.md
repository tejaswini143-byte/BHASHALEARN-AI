# BHASHALEARN AI Architecture Map

Audit date: 2026-11-09. Scope: release-candidate worktree based on INT-18B `4d364d4746ff97356cf26bfefda09903b243831d`. This is a source/OpenAPI map; it is not proof that every feature works at runtime.

## Runtime entrypoints and configuration

- Backend: start from the repository root with `python -m uvicorn backend.app.main:app`. `backend/README.md` says configuration is loaded from the current working directory's `.env`; keep the root `.env` local. Required database and JWT settings are `BHASHALEARN_DATABASE_URL` and `BHASHALEARN_JWT_SECRET_KEY`. DB engine creation is lazy, so a successful process start or `/health` response does not prove database connectivity.
- Frontend: run Vite from `frontend/`. `frontend/vite.config.ts` proxies `/api` and `/health` to `BHASHALEARN_API_PROXY_TARGET`, defaulting to `http://127.0.0.1:8000`. The browser API client uses relative `/api/v1` paths.
- Liveness: `/health` and `/api/v1/health` return a static `status: ok` and do not check DB/provider readiness. `/ready` and `/api/v1/ready` now execute `SELECT 1` using the configured SQLAlchemy engine, return only a generic 503 on DB failure, and do not call AI providers. Their HTTP contract is tested using in-memory SQLite and a simulated failure; connectivity to the authorized PostgreSQL target remains unverified.
- RC dependency resolution: `cryptography 46.0.7` is now installed in the RC private `.venv` from an official PyPI wheel after SHA-256 verification. The first OpenAPI enumeration used an INT-17 `PYTHONPATH` overlay; subsequent app import and HTTP/Playwright validation ran standalone in the RC venv.

## Frontend route map

Routes are declared in `frontend/src/App.tsx`.

| Route | Component / behavior | API relationship |
|---|---|---|
| `/` | Landing page with explicitly labeled UI previews | Preview controls alter local UI state; they are not live provider calls. |
| `/login`, `/register` | `AuthPage` | `frontend/src/auth.ts` calls `/api/v1/auth/login` and `/register`. |
| `/dashboard` | `ProtectedDashboard` | Requires token and loads current student/dashboard data. |
| `/classroom` | `Classroom` | Authenticated session creation, tutor chat, and persisted message history. |
| `/voice`, `/immersive`, `/teacher` | Voice / immersive classroom / teacher preview | Voice API exists; real Prisma/Timbre and a licensed realistic avatar are not acceptance-verified. `/teacher` is currently a prototype preview. |
| `/visual`, `/visual-lessons`, `/chat`, `/documents`, `/knowledge-studio` | Visual studio, interactive lessons, chat, PDFs, knowledge studio | Backend routes exist for session visual context, documents, indexing/search, and knowledge questions; real PostgreSQL/provider end-to-end acceptance remains outstanding. |
| `/quizzes`, `/progress-analytics`, `/memories`, `/missions`, `/career`, `/research`, `/assistant`, `/future-me` | Feature pages | Corresponding API routers are mounted for quizzes, analytics, memories, missions, career, research, and assistant. `/future-me` is a distinct simulator route. |
| `/explore`, `/about`, unknown route | `Explore` placeholder | The page explicitly says upcoming phases are being developed. It is not a feature page. |

Landing-page feature cards and experience tabs are previews; the voice orb is explicitly marked “UI DEMO”. These controls should not be counted as the live classroom journey. The core authenticated route is `/dashboard` → `/classroom`.

## API and persistence contracts

FastAPI mounts all routers under `/api/v1` in `backend/app/main.py`. The generated OpenAPI schema enumerates authentication, student preferences/profile, courses/lessons, sessions/messages/context, tutor, memories, progress/analytics, assessments/quizzes, missions, voice, documents, knowledge, research, career, and assistant endpoints.

The verified core contract is:

1. `POST /api/v1/auth/register` accepts `email`, `display_name`, `password`; returns student fields with HTTP 201.
2. `POST /api/v1/auth/login` accepts `email`, `password`; returns `access_token` and `token_type`; invalid credentials return 401.
3. `GET /api/v1/auth/me` requires `Authorization: Bearer <token>` and returns the authenticated student.
4. `POST /api/v1/sessions` creates the student's learning session.
5. `POST /api/v1/tutor/sessions/{session_id}/chat` requests a tutor turn; the endpoint checks session ownership and persists user/assistant messages on success.
6. `GET /api/v1/sessions/{session_id}/messages` reads the saved turn history.

`frontend/src/auth.ts` stores the JWT in `sessionStorage`, sends it as a bearer token through authenticated feature clients, and maps network failures into a visible connection error. This is session-scoped browser storage, not an HttpOnly cookie.

Core SQLAlchemy tables include `students`, `learning_sessions`, `chat_messages`, `student_preferences`, `learning_progress`, `learning_memories`, `session_visual_states`, and `session_voice_states`. Additive feature tables cover documents/index generations/chunks, career goals/progress, research sessions/sources/tasks/audit, and assistant settings/jobs/accounts/drafts/audit/OAuth state/calls/calendar records.

Candidate Alembic chain (graph only; not applied here):

`0001_initial_schema` → `0002_student_preferences` → `0003_lessons` → `0004_learning_memories` → `0005_session_visual_state` → `0006_adaptive_learning_memory` → `0007_private_documents` → `0008_document_embeddings` → `0009_learning_pace` → `0010_mission_completions` → `0011_int24_research` → `0011_int21_career_roadmap` → `0012_int21_learning_progress` → `0013_int20_session_voice_state` → `0014_int17_assistant` → `0015_int17_provider_integrations`.

The two `0011_*` identifiers are distinct revisions in a linear chain (the INT-21 revision depends on the INT-24 revision); this is not a duplicate revision ID. The current graph's sole head was read-only verified as `0015_int17_provider_integrations`. No PostgreSQL migration was run. Fresh-database and upgrade-with-data acceptance remain required.

## Provider boundaries

- Gemini tutoring is server-side in `backend/app/services/tutor.py`; configured default model is `gemini-3.5-flash-lite`, `generateContent`, 30-second request timeout, and no application retry. `BHASHALEARN_GEMINI_API_KEY` stays backend-only. The test stub is explicit and labeled; it is not live AI evidence.
- Document embedding/indexing uses `BHASHALEARN_GEMINI_EMBEDDING_API_KEY` (falls back to the tutor key when blank per backend documentation), default model `gemini-embedding-001`, 768 dimensions. Indexing/search may make provider requests and requires explicit test approval.
- Gnani voice provider reads server-side `GNANI_*` configuration. Prisma STT and Timbre TTS are separate endpoints from the text chat turn; voice transcript is sent to tutor separately so a turn is persisted once. No live Gnani acceptance is established.
- Research uses its configured adapter boundary; live Brave/Gemini research has not been called. Assistant Google OAuth and Twilio integrations are guarded by explicit settings; live operation flags default off. No external communication was attempted.

## Gaps identified

- Static `/health` can return 200 while DB access fails; the new `/ready` endpoints now expose sanitized DB readiness, but must still be checked against the exact authorized PostgreSQL test target.
- Standalone runtime startup now passes after verified cryptography installation; full PostgreSQL migrations/auth and live provider integration remain unverified.
- The recovery environment's configured database identity/credentials do not match the authorized target, so current-candidate PostgreSQL migration, auth persistence, and Gemini test prerequisites are not satisfied.
- Course catalog GETs are public in the OpenAPI schema by design; course creation is authenticated. Admin/author authorization is explicitly deferred in `courses.py` and must be addressed before public deployment.
- OAuth callback and Twilio webhook are intentionally unauthenticated in OpenAPI; code verifies one-time OAuth state and Twilio request signature/account identity respectively. Their live behavior remains untested.
- Visible marketing preview controls remain local UI state by design; release acceptance must distinguish them from working student controls.
- Voice provider calls, RAG grounding, real Gemini tutoring, integration side-effect security, and both teacher appearance modes remain unverified as documented in the feature matrix.
