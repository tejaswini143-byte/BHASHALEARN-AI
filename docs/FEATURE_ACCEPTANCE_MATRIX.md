# Feature acceptance matrix

The integration candidate does not contain an authoritative INT-01 through INT-30 scope list. This matrix preserves IDs only where repository documentation explicitly names them; it does not guess the meaning of missing IDs. The feature coverage below is tied to named tests and must not be read as a declaration that all thirty INT tickets are complete.

| Feature/workflow | Repository-confirmed ID | Acceptance evidence in repository | Candidate status from this QA pass |
| --- | --- | --- | --- |
| Registration, login, protected dashboard, sessions | INT-01 (`backend/INT01_VALIDATION.md`) | `auth.spec.ts`, `dashboard.spec.ts`, `submission-acceptance.spec.ts`; backend auth/session tests | Browser mock checks reported below; live database/browser checks not rerun. |
| Gnani voice controls and teacher playback sync | INT-03 (`frontend/FE06_VOICE_README.md`); INT-10C is used by voice/avatar E2E spec | `int-10c-voice-avatar.spec.ts`, `voice-contract.test.mjs`, backend `test_voice.py` | Browser provider responses mocked; no live Prisma STT. |
| Shared multimodal session context | INT-04 (`docs/INT-04-multimodal-session-sync.md`) | `backend/tests/test_multimodal_context.py`; frontend classroom/voice/visual tests | Existing tests; backend execution not repeated in this pass. |
| Adaptive tutor, evidence and memory | INT-05 (`docs/INT-05-adaptive-learning-memory.md`) | `test_int05_tutor_acceptance.py`, adaptive/progress/memory suites | Existing tests; backend execution not repeated. |
| Runtime configuration and credentials | INT-06 (`docs/INT-06-runtime-configuration.md`) | `backend/tests/test_runtime_config.py`, `test_db_preflight.py` | Existing tests; backend execution not repeated. |
| Mission mode | INT-11 (Git history and mission tests) | `missions.spec.ts`, `MissionMode` unit tests, backend mission tests | Existing browser/unit coverage; no new database run. |
| Student progress analytics | INT-14 (`backend/INT14_ANALYTICS.md`) | `progress-analytics.spec.ts`, `progress-analytics.test.mjs`, backend analytics tests | Existing browser/unit coverage; analytics explicitly labels unavailable provider data. |
| Holographic teacher preview | INT-19 (Git history) | `teacher.spec.ts`, `teacher.test.mjs`, `int-10c-voice-avatar.spec.ts` | Existing browser/unit coverage; 3D and synthetic demo only. |
| PDF upload/extraction/indexing/search/RAG | ID mapping not present in candidate docs | `documents.spec.ts`, `adv02-indexing.spec.ts`, `test_rag_tutor_api.py`, `test_document_indexing.py`, new mock search acceptance | UI search and citation behavior tested with a clearly synthetic response; live embedding/RAG provider not tested. |
| Classroom bilingual tutoring | ID mapping not present in candidate docs | New `submission-acceptance.spec.ts`; backend tutor tests | Browser exchange and persistence response mocked. |
| Assistant/chat workspace | ID mapping not present in candidate docs | `frontend/e2e/submission-acceptance.spec.ts`, backend tutor/session tests | Browser mock contract checked; no live AI provider call. |
| Quiz workflow | ID mapping not present in candidate docs | `quizzes.spec.ts`, `quizzes.test.mjs`, backend quiz tests | Existing browser/unit coverage; this pass did not rerun the full browser suite. |
| Career roadmap / Future Me | ID mapping not present in candidate docs | `future-me.spec.ts`, `future-me.test.mjs` | Existing browser/unit coverage; deterministic branching scenario, not a career prediction. |
| Teacher selection, lessons, learning profile, visual workflows | ID mapping not present in candidate docs | `teacher.spec.ts`, `visual-lessons.spec.ts`, `learning-profile.spec.ts`, visual lesson unit tests | Existing browser/unit coverage; no external provider claim. |
| Other INT-02, INT-07–10, INT-12–13, INT-15–18, INT-20–30 | Not identified by available authoritative documentation | Scope unavailable in candidate | Unmapped. Request the project-owned ticket list before attributing acceptance evidence to these IDs. |

## Coverage rule

An automated test establishes only the behavior it asserts under its stated fixture and environment. Mocked UI tests establish a client/API contract, not provider quality or production integration. A gated/skipped test is not a pass. A feature is not complete until its owner-provided acceptance criteria are mapped and required live/database evidence is recorded.
