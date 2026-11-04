# BHASHALEARN AI

Adaptive Telugu–English learning assistant for the GNANI challenge.

## Roadmap

1. **Architecture & AI proof of concept** — Prisma STT, Timbre TTS, teaching LLM, adaptive learning, shared context, Telugu–English testing.
2. Backend foundation — FastAPI, PostgreSQL, auth, sessions, orchestration, memory/RAG foundations.
3. Frontend — dashboard, AI classroom, voice, visual and chat interfaces.
4. Integration — connect modes and synchronize classroom context.
5. Advanced features — RAG, uploads, animations, quizzes, memory, analytics.
6. Testing & deployment — E2E, security, performance, demo.

## Current scope: Phase 1 / POC-01 (Prisma STT)

The first experiment lives under `pocs/poc01_prisma_stt/`. It is intentionally independent of the production backend. Its adapter boundary can be reused in Phase 2.

**Status:** implementation and offline tests provided; live GNANI request requires your own credentials and endpoint verification.

See [POC-01 setup](pocs/poc01_prisma_stt/README.md) and [Phase 1 tracker](docs/PHASE1_TRACKER.md).

Do not commit API keys or recorded private speech.
