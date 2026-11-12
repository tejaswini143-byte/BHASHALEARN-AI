# BhashaLearn AI — Parallel Codex Worker Handoffs

Prepared 2026-11-09 by CODEX 1 (integration owner).

## Baseline and preservation contract

- RC worktree: `C:/Users/Tejaswini/BHASHALEARN-INT26/_integration_rc_20261109`
- RC branch: `integration/release-candidate-20261109`
- RC committed HEAD: `4d364d4746ff97356cf26bfefda09903b243831d` (`fix: keep integrated dashboard navigation reachable`)
- Worktree inventory at setup: 32 registered worktrees. Existing paths and their contents are preserved.
- Provisioning result: seven sibling worktrees/branches were added successfully; the repository now registers 39 worktrees. Each new checkout is clean at the exact RC committed HEAD. The per-checkout verification used path-scoped `safe.directory` only; no global Git settings were changed.
- The new branches are created from the committed RC HEAD only. The RC audit found 95 pre-existing Git status entries, all outside that commit. This handoff file adds one untracked documentation entry in the RC; none of those RC entries are copied to workers.
- No database, local environment file, provider secret, or existing test artifact is to be copied. Git worktrees check out committed files only; the tracked environment files found are `.env.example` templates.
- Never reset, clean, stash, overwrite, or discard existing state. Do not edit the RC worktree. No worker may push, deploy, delete data, or make unapproved live provider calls.

## Audit snapshot

The read-only `git worktree list --porcelain` and per-worktree `git status --porcelain` audit found 32 registered paths. Clean worktrees: ADV01–ADV07, INT05-REMOTE, INT09, INT10A/B/C, INT11–INT12, INT14–INT15, INT19–INT20, INT22–INT24. Dirty worktrees and status paths:

| Existing worktree | Branch / HEAD | Git status entries and notable paths |
|---|---|---|
| `C:/Users/Tejaswini/BHASHALEARN-AI` | `feature/int-05-adaptive-learning` / `e542103` | 2: `frontend/README.md`, `.venv.broken-backup/` |
| `C:/Users/Tejaswini/BHASHALEARN-CLASSROOM` | `feature/unified-ai-classroom` / `70154c7` | 5 preserved Playwright/test result directories |
| `C:/Users/Tejaswini/BHASHALEARN-INT13` | `feature/int-13-adaptive-quizzes` / `9bbeed8` | 9 preserved Playwright reports/results |
| `C:/Users/Tejaswini/BHASHALEARN-INT16` | `feature/int-16-teaching-intelligence` / `3aaaaa3` | 2 preserved test-result directories |
| `C:/Users/Tejaswini/BHASHALEARN-INT17` | `feature/int-17-personal-assistant` / `028bb27` | 6 preserved test-result directories |
| `C:/Users/Tejaswini/BHASHALEARN-INT18B` | `feature/int-18b-unified-integration` / `4d364d4` | 5 preserved test-result directories |
| `C:/Users/Tejaswini/BHASHALEARN-INT21` | `feature/int-21-career-roadmap` / `3701823` | 6 preserved Playwright result directories |
| `C:/Users/Tejaswini/BHASHALEARN-INT25` | `feature/int-25-communication-orchestration` / `70154c7` | 1: `docs/INT-25-communication-orchestration-audit.md` |
| `C:/Users/Tejaswini/BHASHALEARN-INT26` | `feature/int-26-holoos-polish` / `70154c7` | 18, including `frontend/src/App.tsx`, `Classroom.tsx`, `Dashboard.tsx`, `main.tsx`, `HoloUI.tsx`, adapters, navigation, tests, and preserved reports. This path is distinct from the RC child worktree. |
| `C:/Users/Tejaswini/BHASHALEARN-INT26/_integration_rc_20261109` | `integration/release-candidate-20261109` / `4d364d4` | 95 entries. Modified: backend `.env.example`, README, tutor/voice/config/models/main, document-index/RAG services, requirements/tests; `docs/ADV-06-voice-architecture.md`; frontend voice E2E, `App.tsx`, `Classroom.tsx`, `Dashboard.tsx`, `VoiceTutor.tsx`, `main.tsx`. Untracked: `.test-tmp/`; Alembic `0011_int21_career_roadmap`, `0011_int24_research`, `0012_int21_learning_progress`, `0013_int20_session_voice_state`, `0014_int17_assistant`, `0015_int17_provider_integrations`; assistant/career/knowledge/research backend APIs/services/tests; architecture/status/security/test docs; frontend assistant/career/HoloUI/knowledge/research components and styles, `frontend/src/dashboard/`, E2E/unit tests, debug output, Playwright reports and test-result folders. **All remain exclusively in the RC.** |
| `C:/Users/Tejaswini/BHASHALEARN-INT26/_phaseb_int18b_test` | `recovery/phase-1-student-journey-test` / `4d364d4` | 6 preserved `.phaseb-postgres/` and frontend browser/cache/report directories |

The `INT05-REMOTE` worktree is detached at `650bc4f`; all others have the branches and HEADs shown in `git worktree list`. There are no pre-existing paths at the seven planned new targets below. The target branches are new and unique.

## Worker ownership and setup status

Worker directory targets are siblings of the existing project worktrees, not directories inside the RC or any existing worktree. Each worker owns only its listed paths. A worker must coordinate with CODEX 1 before touching shared app entrypoints, authentication, migrations, or central configuration. The new worktree paths and branches are provisioned by CODEX 1 after this handoff file is written.

| Worker | Worktree | Branch | Assigned files / ownership fence | Dependencies | Status |
|---|---|---|---|---|---|
| CODEX 1 | `C:/Users/Tejaswini/BHASHALEARN-INT26/_integration_rc_20261109` | `integration/release-candidate-20261109` | Integration, PostgreSQL/Alembic, shared entrypoints/config/auth, release acceptance | Worker commits and evidence; integration by CODEX 1 only | Active owner; RC dirty state preserved |
| CODEX 2 | `C:/Users/Tejaswini/BHASHALEARN-CODEX2-20261109` | `feature/codex-2-gnani-voice` | `backend/app/services/gnani_voice.py`, `frontend/src/VoiceTutor.tsx`, `voiceContract.ts`, `voice.css`; voice-focused tests only when isolated to their own new files | Existing voice API contract; coordinate any API/config/migration need with CODEX 1; no live provider request without approval | Ready after worktree provisioning |
| CODEX 3 | `C:/Users/Tejaswini/BHASHALEARN-CODEX3-20261109` | `feature/codex-3-teacher-modes` | `frontend/src/TeacherPreview.tsx`, `teacherCore.ts`, `teacher-preview.css`, and new teacher-mode-local components/tests/assets metadata | Rights-cleared rigged model needed for realism; no model currently recorded in audit. Label procedural preview honestly; coordinate shared classroom integration with CODEX 1 | Ready after worktree provisioning |
| CODEX 4 | `C:/Users/Tejaswini/BHASHALEARN-CODEX4-20261109` | `feature/codex-4-qa-submission` | New submission docs under `docs/` (use `SUBMISSION-INT01-30.md` and `DEMO-SCRIPT.md`) and QA/E2E specs under `frontend/e2e/codex4-*.spec.ts`; never edit product source | Stable RC acceptance contracts from CODEX 1; isolated test DB/ports; evidence retained in unique paths | Ready after worktree provisioning |
| CODEX 5 | `C:/Users/Tejaswini/BHASHALEARN-CODEX5-20261109` | `feature/codex-5-gemini-tutor` | `backend/app/services/tutor.py`, `teaching_intelligence.py`, `adaptive_learning.py`, `personalizedTeaching.ts`, `PersonalizedLessonPlan.tsx`, `LearningProfilePanel.tsx`; new feature-local tests | Existing tutor API; provider-off deterministic tests. Coordinate API/auth/config changes with CODEX 1; no live Gemini call without approval | Ready after worktree provisioning |
| CODEX 6 | `C:/Users/Tejaswini/BHASHALEARN-CODEX6-20261109` | `feature/codex-6-rag-lessons` | `backend/app/services/{documents.py,chunking.py,embeddings.py,document_index.py,rag_tutor.py,visual_lessons.py}`, `frontend/src/{Documents.tsx,documentModel.ts,KnowledgeStudio.tsx,VisualLessons.tsx,VisualStudio.tsx,visualLessonsModel.ts}` and feature styles/new tests | Existing knowledge/visual API contracts; schema or migration work only after CODEX 1 agreement; isolated test DB | Ready after worktree provisioning |
| CODEX 7 | `C:/Users/Tejaswini/BHASHALEARN-CODEX7-20261109` | `feature/codex-7-student-workspace` | `backend/app/services/{career_roadmap.py,research.py,research_adapters.py,assistant_google.py,assistant_providers.py,assistant_worker.py}`, `frontend/src/{CareerRoadmap.tsx,careerModel.ts,ResearchWorkspace.tsx,AssistantDashboard.tsx}`, their feature-local styles and tests | Existing feature APIs; database/schema/migration and provider configuration changes require CODEX 1 coordination; provider-off tests | Ready after worktree provisioning |
| CODEX 8 | `C:/Users/Tejaswini/BHASHALEARN-CODEX8-20261109` | `feature/codex-8-holoos-ui` | `frontend/src/HoloUI.tsx`, `holo-ui.css`, `holo-polish.css`, and new isolated HoloOS presentation/accessibility components/tests. Do not edit `App.tsx`, `main.tsx`, `Classroom.tsx`, `Dashboard.tsx`, `auth.ts`, or shared navigation without CODEX 1 approval | Shared entrypoint integration through CODEX 1; existing route behavior and responsive/accessibility requirements | Ready after worktree provisioning |

The listed files describe ownership, not a requirement to rewrite each file. Start by inspecting the committed baseline and targeted tests. Existing RC uncommitted files do not appear in a new worker checkout; where those paths overlap RC modifications, expect CODEX 1 to reconcile the branch diff against the RC candidate during integration.

## Common worker rules

1. Work only in the assigned worktree and branch. Never edit another worker's worktree or the RC worktree.
2. Do not push or deploy. Do not delete or alter databases, credentials, local artifacts, or services. Do not make live provider calls unless CODEX 1 has obtained explicit approval.
3. Never commit secrets, `.env` files, databases, generated bundles, or test evidence. Use an isolated test database and unique test ports. Keep Playwright/evidence output in unique, non-overwriting directories and report exact paths.
4. Do not edit shared app entrypoints, auth, Alembic migrations, central configuration, or dependency manifests without first coordinating with CODEX 1. Do not make conflicting cross-worker edits; ask CODEX 1 to assign additional paths.
5. Distinguish mocks from real integrations in code, UI, documentation, and evidence. Do not claim live/provider acceptance based on mocks.
6. Make small, reviewable commits. Run only the targeted tests relevant to the change, retain evidence, and report test command/result. Before handoff, provide branch, exact commit hash(es), changed paths, integration dependencies/conflicts, setup requirements, and known gaps. CODEX 1 alone integrates.

## Copy-paste prompts

### CODEX 2 — Gnani voice

```text
You are CODEX 2 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX2-20261109 on feature/codex-2-gnani-voice. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own the Gnani Prisma STT, Timbre TTS, bilingual voice behavior, and interruption handling. First inspect the existing committed voice service, VoiceTutor contract/UI, and focused tests. Limit edits to backend/app/services/gnani_voice.py, frontend/src/VoiceTutor.tsx, frontend/src/voiceContract.ts, frontend/src/voice.css, and new voice-specific tests. Do not edit shared app entrypoints, API routes, auth, migrations, central config, or dependency manifests without CODEX 1 coordination. RC has uncommitted edits to voice APIs/config/UI/tests; do not touch that worktree or try to copy its files into your branch.

Keep providers disabled by default and use mocks for tests. Do not make live Prisma/Timbre calls or copy provider credentials. Clearly label mocked behavior and never claim real-provider acceptance without recorded approved evidence. Use isolated test data/ports and retain evidence in a unique path. Make small commits; run focused tests only. Handoff exact commit hash(es), changed files, targeted test commands/results, evidence paths, and API/config/integration requirements to CODEX 1. Do not push or deploy.
```

### CODEX 3 — Teacher modes

```text
You are CODEX 3 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX3-20261109 on feature/codex-3-teacher-modes. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own realistic/holographic teacher presentation, animation, and lip sync. Inspect TeacherPreview, teacherCore, styles, and focused tests first. Limit changes to frontend/src/TeacherPreview.tsx, frontend/src/teacherCore.ts, frontend/src/teacher-preview.css, plus new teacher-mode-local components/tests and rights/license metadata. No rights-cleared rigged human model is recorded in the audit; do not fabricate an asset or claim realism. Improve procedural mode honestly, provide a clear asset-ready interface/fallback, and report the external asset dependency. Keep changes local to the teacher experience; coordinate shared classroom entrypoints with CODEX 1 before any edit. Never change auth, migrations, central config, or another worker's files.

Use local/mock animation inputs, label demonstrations accurately, and retain test evidence under unique paths. Make small commits and run targeted tests only. Handoff exact commit hash(es), paths, test commands/results, asset/licensing requirement, and integration notes to CODEX 1. Do not push or deploy.
```

### CODEX 4 — QA and submission materials

```text
You are CODEX 4 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX4-20261109 on feature/codex-4-qa-submission. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own QA, Playwright acceptance coverage, submission documentation, and a concise demo script. Limit changes to new docs/SUBMISSION-INT01-30.md and docs/DEMO-SCRIPT.md plus new frontend/e2e/codex4-*.spec.ts specs and isolated QA helpers. Do not edit product source, shared app entrypoints, auth, migrations, central configuration, or existing test/evidence directories. Inspect current acceptance docs and existing flows first. Tests must use isolated databases and unique ports; keep reports/evidence in unique non-overwriting paths. Do not use real provider calls unless CODEX 1 confirms approval. Separate mocked acceptance from real-provider/runtime/database evidence and identify gaps without implying mocks are real.

Make small reviewable commits and run targeted Playwright or documentation validation only. Handoff exact commit hash(es), changed files, commands/results, preserved evidence paths, and any acceptance dependencies to CODEX 1. Do not push or deploy.
```

### CODEX 5 — Gemini tutor and adaptive learning

```text
You are CODEX 5 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX5-20261109 on feature/codex-5-gemini-tutor. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own Gemini tutor behavior, bilingual teaching, and adaptive learning. Start by inspecting committed tutor, teaching_intelligence, adaptive_learning, personalizedTeaching, PersonalizedLessonPlan, LearningProfilePanel, and focused tests. Limit edits to backend/app/services/tutor.py, teaching_intelligence.py, adaptive_learning.py, frontend/src/personalizedTeaching.ts, PersonalizedLessonPlan.tsx, LearningProfilePanel.tsx, and new isolated tests for this feature. No live Gemini request is approved; keep provider-off deterministic tests and report mock/live boundaries. Coordinate API/auth/config/dependency/migration needs with CODEX 1 before touching shared files. Do not touch the RC worktree or another worker's ownership.

Use isolated test database/ports, preserve evidence at unique paths, make small commits, and run targeted tests only. Handoff exact commit hash(es), paths, test commands/results, any contract/schema integration requirement, and known gaps to CODEX 1. Do not push or deploy.
```

### CODEX 6 — PDF RAG, visual lessons, quizzes, analytics

```text
You are CODEX 6 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX6-20261109 on feature/codex-6-rag-lessons. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own PDF ingestion/RAG, visual lessons, quizzes, and learning analytics. Inspect the committed document, embedding, RAG, visual lesson, quiz, and progress modules and their focused tests. Primary ownership is backend/app/services/documents.py, chunking.py, embeddings.py, document_index.py, rag_tutor.py, visual_lessons.py; frontend/src/Documents.tsx, documentModel.ts, KnowledgeStudio.tsx, VisualLessons.tsx, VisualStudio.tsx, visualLessonsModel.ts; their feature-local styles; and new isolated tests. Avoid edits to shared routes, models, migrations, config, or package manifests unless CODEX 1 coordinates them. Keep document processing and tutor/visual claims grounded in actual behavior; clearly label mocks.

Use synthetic PDFs/data, isolated test DB/ports, and unique retained evidence paths. No live external calls unless explicitly approved by CODEX 1. Make small commits and run targeted tests only. Handoff exact commit hash(es), changed paths, test commands/results, evidence paths, and schema/API dependencies to CODEX 1. Do not push or deploy.
```

### CODEX 7 — Career, research, personal assistant

```text
You are CODEX 7 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX7-20261109 on feature/codex-7-student-workspace. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own career roadmap, research workspace, and personal assistant. Inspect committed implementations and focused tests first. Primary ownership is backend/app/services/career_roadmap.py, research.py, research_adapters.py, assistant_google.py, assistant_providers.py, assistant_worker.py; frontend/src/CareerRoadmap.tsx, careerModel.ts, ResearchWorkspace.tsx, AssistantDashboard.tsx; their feature-local styles; and new isolated tests. Keep edits inside these areas. Do not edit shared app entrypoints, routes, auth, models, migrations, central config, or dependency manifests without prior CODEX 1 coordination. Never call external search, Gmail, Calendar, Gemini, or other live provider integrations without explicit approval; provider-off tests must say they are mocks.

Use isolated test databases/ports and unique preserved evidence paths. Make small commits; run targeted tests only. Handoff exact commit hash(es), changed files, test commands/results, evidence paths, and API/schema/provider integration needs to CODEX 1. Do not push or deploy.
```

### CODEX 8 — HoloOS UI

```text
You are CODEX 8 for BhashaLearn AI. Work only in C:/Users/Tejaswini/BHASHALEARN-CODEX8-20261109 on feature/codex-8-holoos-ui. Base HEAD is 4d364d4746ff97356cf26bfefda09903b243831d. CODEX 1 is the sole integration owner.

Own HoloOS presentation polish, responsive design, accessibility, and navigation design proposals. Inspect committed HoloUI/styles and existing accessibility/navigation coverage. Limit edits to frontend/src/HoloUI.tsx, holo-ui.css, holo-polish.css, plus new isolated presentation/accessibility components and tests. Do not edit App.tsx, main.tsx, Classroom.tsx, Dashboard.tsx, auth.ts, shared routing/navigation, migrations, or central config without CODEX 1 coordination. RC and the existing INT26 worktree both have active UI/navigation changes; leave them untouched. Provide any routing changes as a proposal or isolated adapter for CODEX 1 to integrate.

Keep keyboard, screen-reader, reduced-motion, contrast, and narrow-screen behavior covered by focused tests. Use isolated test ports and unique retained evidence paths. Make small commits and run targeted tests only. Handoff exact commit hash(es), changed paths, commands/results, evidence paths, and integration needs to CODEX 1. Do not push or deploy.
```

## Launching worker sessions

After provisioning, start seven separate Codex sessions and open each session at its matching worktree path above. Paste that worker's prompt from this document. On Windows PowerShell, a worker can verify its checkout with `git status --short --branch` and `git rev-parse HEAD`. Keep each session rooted in its own directory. CODEX 1 retains the RC session and integrates reviewed commits by exact hash after checking each diff and its evidence.

## Provisioning ledger

| Worker | Created path | Branch | Created HEAD | Commit(s) returned | Integration disposition |
|---|---|---|---|---|---|
| CODEX 2 | `C:/Users/Tejaswini/BHASHALEARN-CODEX2-20261109` | `feature/codex-2-gnani-voice` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 3 | `C:/Users/Tejaswini/BHASHALEARN-CODEX3-20261109` | `feature/codex-3-teacher-modes` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 4 | `C:/Users/Tejaswini/BHASHALEARN-CODEX4-20261109` | `feature/codex-4-qa-submission` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 5 | `C:/Users/Tejaswini/BHASHALEARN-CODEX5-20261109` | `feature/codex-5-gemini-tutor` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 6 | `C:/Users/Tejaswini/BHASHALEARN-CODEX6-20261109` | `feature/codex-6-rag-lessons` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 7 | `C:/Users/Tejaswini/BHASHALEARN-CODEX7-20261109` | `feature/codex-7-student-workspace` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
| CODEX 8 | `C:/Users/Tejaswini/BHASHALEARN-CODEX8-20261109` | `feature/codex-8-holoos-ui` | `4d364d4746ff97356cf26bfefda09903b243831d` | pending | Ready for isolated work |
