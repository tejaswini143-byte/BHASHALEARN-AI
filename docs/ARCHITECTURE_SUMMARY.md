# BHASHALEARN AI architecture summary

BHASHALEARN AI is a student-facing bilingual learning app with a React/Vite browser client and a FastAPI backend.

## Request and data flow

```text
Browser (React Router)
  ├─ Vite /api proxy in local development
  └─ authenticated JSON or multipart requests
        ↓
FastAPI /api/v1
  ├─ auth, student preferences, sessions and saved messages
  ├─ tutor and teaching-plan orchestration
  ├─ assessments, quizzes, progress, missions and analytics
  ├─ private PDF extraction, indexing and semantic search
  └─ speech endpoints → Gnani Prisma STT / Timbre TTS adapters
        ↓
PostgreSQL + pgvector (documents, sessions and learning evidence)
```

The browser stores the bearer access token in session storage and sends it to protected APIs. Sessions are the shared context boundary for classroom chat, voice, visual lessons and related teaching flows. Backend API routers are registered in `backend/app/main.py`; provider configuration is centralized in the backend settings and adapters.

## Provider boundaries

| Capability | Boundary | Evidence status |
| --- | --- | --- |
| Tutor text and personalized plans | Backend Gemini adapter | API and mock tests exist; this QA run did not make live Gemini calls. |
| PDF embeddings and semantic search | Explicit indexing/search routes using Gemini embeddings | Deterministic fake embedding option exists for isolated tests; no live call in this QA run. |
| Speech transcription | Authenticated voice endpoint → Gnani Prisma adapter | Contract and mocked tests exist; no live Prisma acceptance in this run. |
| Speech synthesis | Authenticated speech endpoint → Gnani Timbre adapter | Contract and mocked tests exist; historical POC docs record live generation; not repeated here. |
| Teacher animation and smartboard | Local browser state, playback clock and validated lesson commands | UI/unit acceptance exists; synthetic viseme demo is not provider-generated speech. |

## Data and privacy boundaries

User and session data belongs to the authenticated student. PDF files remain in private storage; extracted text is submitted to the embedding provider only when the user explicitly indexes or searches. Tests must use disposable PostgreSQL, separate storage, synthetic PDF fixtures, and mocks or a clearly marked test provider. Do not put provider keys or private recordings in source control.
