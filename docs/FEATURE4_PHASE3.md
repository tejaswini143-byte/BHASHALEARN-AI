# Feature 4 — Phase 3: Authenticated visual lesson API

## Implemented
- `GET /api/visual-lessons`: list three curated bilingual lesson envelopes.
- `GET /api/visual-lessons/{lesson_id}`: fetch a specific envelope; unknown IDs return 404.
- Both routes require authenticated student access.
- Pydantic strict schemas reject unsupported fields, missing translations, mismatched scene kinds and unsupported versions.
- Backend tests for catalog invariants, malformed envelopes and anonymous access.

## Scope boundary
This is a **curated catalog API**, not live LLM-generated lesson content. AI generation, storage, personalization and syncing the existing frontend catalog to the API remain Phase 4 integration work. The backend content currently mirrors the three simulation topics but is not a byte-for-byte copy of the frontend teaching text.

## Verification
Run `python -m pytest -q backend/tests/test_feature4_visual_lessons.py` from the repository root and the existing backend regression suite. Verify the configured API prefix is `/api`; if configured differently, update the route smoke test accordingly. No test or deployment execution was possible through the GitHub file connector.
