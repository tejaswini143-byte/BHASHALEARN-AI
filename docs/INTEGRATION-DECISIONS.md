# Integration Decisions and Safety Log

## Baseline and isolated worktree

- Source baseline: INT-18B `4d364d4746ff97356cf26bfefda09903b243831d`.
- Created branch `integration/release-candidate-20261109` and worktree `C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109` only after confirming the destination and branch did not exist.
- No source commits have been created or merged. INT-22 commit `f4abd85` has been applied as uncommitted candidate changes under `frontend/src/Dashboard.tsx`, `frontend/src/dashboard/`, and `frontend/e2e/command-center.spec.ts`; no existing worktree has been edited, reset, cleaned, stashed, or rebased.
- The recovery worktree remains separate and untouched.

## Worktree state observed

- Original project `BHASHALEARN-AI`: modified `frontend/README.md`, untracked `.venv.broken-backup/`.
- `BHASHALEARN-CLASSROOM`: untracked historical Playwright result directories.
- INT-13, INT-16, INT-17, INT-18B, INT-21: untracked historical browser reports/results.
- INT-25: untracked `docs/INT-25-communication-orchestration-audit.md`.
- INT-26: modified `future-me.spec.ts`, `App.tsx`, `Classroom.tsx`, `Dashboard.tsx`, `main.tsx`, and `future-me.test.mjs`; untracked `navigation.spec.ts`, Holo UI components/styles, historical test results, and the Phase B recovery directory.
- Phase B recovery: untracked `.phaseb-postgres/`, frontend npm cache, and browser report/result directories. All preserved.
- Other registered worktrees showed no tracked/untracked status lines at inventory time.

The full worktree/branch inventory was obtained from `git worktree list --porcelain`, `git branch --list`, and per-worktree `git status --short --branch`. No `INT-27` worktree was registered.

## Services and database boundary

- Direct localhost HTTP: stub backend `127.0.0.1:8016/health` = 200; frontend `127.0.0.1:5188/` = 200.
- PostgreSQL listeners observed on 55432 and 5432. Only 55432 is the approved isolated service; 5432 was not queried or modified.
- The recovery `.env` currently resolves to `127.0.0.1:55432/bhashalearn_phaseb_9991cde0ee`, not the authorized `bhashalearn_phaseb_e2e_96ce964941`. Authentication to the configured database failed. No database mutations or app writes were made during this audit.
- Historical Phase B evidence records Alembic `0010_mission_completions` and pgvector 0.8.7 for the authorized DB in the earlier verified run. The current config mismatch means that revision was not re-read in this turn.
- Do not migrate, create/drop databases, or use the mismatched target. Restore a matching config and verify identity/revision read-only first.

## Provider boundary

- Previous Phase C approval covered at most one live Gemini `generateContent` request. That request has not occurred.
- A non-placeholder key value is in the ignored recovery `.env`, but format/validity is unconfirmed. It was never printed. No Gemini or Gnani request was sent.
- The recovery config has no separate Gemini embedding credential and no Gnani credential. INT-18B documents `gemini-2.5-flash`, `gemini-embedding-001`, Prisma `prisma-v3.0`, and Timbre `timbre-v2.5`; endpoint/timeouts and variable names are in `backend/.env.example`. These are configured defaults, not proof of live provider availability.
- The local tutor adapter uses `gemini-2.5-flash`, `generateContent`, 30-second timeout, max 800 output tokens, and no application retry. The chat route avoids an embedding provider call only when no document index is ready; current DB state could not be read because configured credentials failed.
- No provider or external communication beyond the one-call approved scope is authorized.

## Feature branch lineage and migration collisions

- INT-17, INT-19, INT-20, INT-22, INT-23, and INT-24 feature commits are based at `70154c7`, an ancestor of INT-18B. Compare each feature delta from its actual merge base; a direct tree diff against INT-18B misleadingly shows unrelated later INT-18B additions as removals.
- INT-21 contains two commits on the same lineage. INT-26's working branch also points at `70154c7` and its local modifications are uncommitted; preserve and review those exact edits separately.
- Branches INT-17, INT-20, INT-21, and INT-24 each add separate Alembic children of `0010_mission_completions` (different revision IDs, multiple heads rather than duplicate IDs); INT-17 and INT-21 also define follow-on revisions. The candidate now chains INT-24 `0011_int24_research` → INT-21 `0011_int21_career_roadmap` → INT-21 `0012_int21_learning_progress`. Read-only `alembic heads` reports the sole head `0012_int21_learning_progress`. Original feature worktrees and migration files remain unchanged; no database migration has been run.
- INT-17 adds OAuth/assistant provider infrastructure and two migrations; all Gmail/Calendar/Twilio actions must remain disabled until security/approval semantics and credentials are reviewed.
- INT-19 explicitly labels its teacher as a stylized geometric proxy and documents the missing rights-cleared rigged asset. Do not treat this branch as the requested realistic teacher or integrate it as a release-ready replacement.
- INT-20 adds voice-session checkpoints, interruption/resume UI, provider-readiness reporting, request limits, and language override. The RC now contains an adapted backend/model, `0013_int20_session_voice_state` chained after `0012_int21_learning_progress`, serialized frontend checkpoint writes, and interrupt/resume controls. The INT-10C `VoiceTutor` props, local demo behavior, and bridge generation contract were preserved; no wholesale branch overlay was used. The INT-20 worktree itself remains unchanged. SQLite/API tests and a mocked browser checkpoint/resume test pass. No PostgreSQL migration or live Gnani call was made.
- The candidate migration graph remains unapplied on PostgreSQL. Its single Alembic head is `0013_int20_session_voice_state`; exact authorized DB access is still blocked by the recovery `.env` mismatch/authentication failure. The voice API rate limiter is process-local and is not a distributed production rate limit.
- INT-21 adds career roadmap/progress schemas and a dashboard-linked career planner. Its API/UI are integrated in RC, and its two unapplied migrations follow INT-24 in one linear candidate chain. Database upgrade/persistence remains unverified; original feature worktree remains untouched.
- INT-22 is frontend-focused and changes Dashboard composition. Candidate UI acceptance passed with mocked APIs; an authenticated dashboard against the authorized database remains outstanding.
- INT-23 adds an additive `/knowledge` API, document-scoped retrieval filtering, and Knowledge Studio UI. It introduces no migration. The changes are now present as uncommitted RC candidate edits; route ownership/index-readiness, quiz schema, citation, and selected-document tests pass. The browser upload/select/ask/citation flow passed with mocked HTTP. Live PostgreSQL document indexing and real Gemini grounding are still blocked and were not attempted.
- INT-24 adds research storage/API, the `0011_int24_research` child migration, source URL checks, labeled offline fixtures, and draft/approval task proposals that remain `executable=False`. Its focused mocked browser test and backend suite pass; no Brave/Gemini call, migration, or real database persistence test has run.
- INT-21 adds the career roadmap API/UI, evidence-aware skill gaps, catalog lesson completion, and weekly study tracking. Candidate backend/frontend suites and focused browser flow pass; no PostgreSQL migration or persistence test has run.
- INT-25's untracked audit note references an earlier dirty INT-17 state. Current worktree inventory shows INT-17 clean at commit `028bb27`; treat that note as historical, not current source-of-truth.
- INT-26 has a dirty visual polish set plus untracked `HoloUI.tsx`, adapters, styles, navigation E2E, and artifacts. Its original worktree remains untouched. The shared HoloUI primitives/styles/navigation and classroom/dashboard sidebar wrappers have been adapted into the candidate; INT-26-specific Dashboard rewrites remain excluded because they conflict with the newer INT-22 command-center composition.

## INT-22 candidate integration adaptation

- Applied the single INT-22 command-center feature delta into this candidate without a commit. The Dashboard component was manually adapted because its patch did not apply over INT-18B's later dashboard edits.
- The original branch pointed “Adaptive quizzes” to `/classroom`, “Progress analytics” to an in-page anchor, and “Career roadmap” to `/future-me`. The candidate now links quizzes to `/quizzes`, analytics to `/progress-analytics`, and visibly disables the separate roadmap entry until INT-21 is safely integrated. The Future Me card is labeled career scenarios and says the roadmap is not connected.
- A first frontend regression run caught the missing analytics link (63/64 pass); after adding the route link and truthful unavailability states, all 64 passed. The candidate then passed 11 Playwright cases, including dashboard navigation to each configured route, mobile layout, reduced motion, empty data, and mocked service errors.
- These are UI/mock tests; this adaptation has not yet been checked against the live isolated database or the real authenticated student journey.

## INT-26 shared UI adaptation

- Copied only `HoloUI.tsx`, shared HoloOS CSS, and the navigation browser spec into the candidate; adapted the candidate App header/landing CTA, classroom sidebar, and INT-22 dashboard shell. Kept the INT-18B route table and INT-22 dashboard data flow.
- The mobile landing navigation, focus visibility, reduced-motion handling, feature links, and responsive dashboard controls passed in the latest 39-case Playwright run. Frontend unit tests remained 64/64 and the build passed with the existing large Three.js chunk warning.
- Teacher previews and audio timing are simulated in these browser tests. A read-only asset scan found no GLB/GLTF/VRM/FBX file or license record in ADV-05, INT-19, INT-18B, INT-26, or the candidate; realistic teacher acceptance remains blocked on the licensed model dependency.
- The original INT-26 dirty/untracked files and reports were not changed. No full visual review across every route/device has been completed.

## Runtime preparation

The old recovery `.venv` references an inaccessible base interpreter. A private Python 3.12.10 runtime and `backend/requirements.txt` packages were installed in this integration worktree only. No global Python was changed. Candidate source changes in this RC are uncommitted and isolated from all existing worktrees.

## Revalidation on 2026-11-09

- Read-only Git inventory reconfirmed the RC branch/head and all registered INT/ADV worktrees. Existing dirty files and test artifacts remain untouched. For cross-owner worktrees, Git was invoked with a command-scoped `safe.directory=*`; no global Git configuration was changed.
- The recovery backend and frontend remain available at `127.0.0.1:8016` and `127.0.0.1:5188` (both HTTP 200); PostgreSQL is listening at `127.0.0.1:55432`; port 8021 is free. No auth, chat, or other mutating HTTP request was sent.
- The recovery `.env` still targets `bhashalearn_phaseb_9991cde0ee`. A read-only connection attempt addressed only the explicitly authorized `bhashalearn_phaseb_e2e_96ce964941` database at `127.0.0.1:55432` and failed authentication with the configured credentials. No migration or write was attempted and no other database was accessed.
- The approved single Gemini request remains unused. Key presence was observed without displaying its value, but validity is unconfirmed. The database/authentication precondition prevents creating the synthetic authenticated classroom needed for that one call; no provider request was sent.
- INT-09 through INT-16 feature tips are ancestors of the INT-18B baseline, so their committed implementations are already present in the RC base. Their current release acceptance status still depends on feature-specific browser/database/provider verification recorded in the matrix.

## Candidate HTTP journey and INT-17/28 audit continuation — 2026-11-09

- Created a new test-only local SQLite database inside the RC artifact directory and a test-only ASGI entrypoint that creates its schema from SQLAlchemy metadata, sets a process-only random JWT secret, disables provider credentials, overrides embeddings locally, and replaces tutor generation with a deterministic bilingual response clearly labeled as a stub. This is test scaffolding, not an application source change or Alembic migration.
- Started only the RC backend on 8022 and RC Vite frontend on 5193 after confirming both ports were free. A Playwright test passed the real HTTP flow: registration, logout/login, protected dashboard, classroom creation, bilingual local-stub reply, reload persistence, and invalid-login handling. Assertions observed 201 registration, 200 login/auth-me/chat, and 401 invalid login. The isolated file contains synthetic test rows only and passed SQLite integrity. Provider calls were not made.
- Repeated the browser journey against a fresh isolated database after changing the E2E password to a process-memory random value. The final run passed 1/1; independent database checks found exactly one synthetic student/session, two messages with one labeled test-stub reply, and SQLite integrity `ok`. The final database and Playwright result directory are preserved under `.test-tmp/rc-http-journey-20261109-final/` and `frontend/test-results-rc-live-http-20261109-final/`. List-only reporting was selected, so there is no HTML report.
- Preserved all first-attempt and retry test artifacts; no output was overwritten. Stopped the temporary RC processes and rechecked that 8022/5193 are free while the original 8016/5188/55432 services remain available.
- Correction from the refreshed merge-base audit below: INT-17's actual feature delta from its common ancestor with INT-18B is 19 assistant-focused files. A direct tree comparison against the later INT-18B baseline showed roughly 65 differences because INT-17 lacks later baseline additions; those are not INT-17 deletions. The branch's 19-file delta was selectively ported. Migration revisions were appended after the RC head; PostgreSQL acceptance remains pending.
- Read-only ADV-05/INT-19 asset audit confirms the preview explicitly describes itself as procedural geometry and supports loading a local GLB, but no model or license record is present. Do not claim either realistic teacher mode until the rights-cleared rigged human asset is supplied and browser-verified.

## INT-17 selective assistant port — 2026-11-09

- Superseding the earlier “future port” note above: the 19-file assistant feature delta was selectively copied into the RC. The INT-17 source worktree and commit remain untouched; later INT-18B baseline files were preserved.
- Appended assistant migrations as new RC revisions `0014_int17_assistant` and `0015_int17_provider_integrations` after `0013_int20_session_voice_state`. Read-only Alembic inspection reports the sole head `0015_int17_provider_integrations`. No migration was run against PostgreSQL.
- The assistant provider module’s trailing literal `\\n` syntax defect was fixed in the RC copy. The first dependency download failed SHA-256 verification, so the initial test pass temporarily used INT-17's package directory read-only. That is resolved in the later standalone-runtime section: a direct official PyPI wheel matched its published SHA-256 and was installed only into the RC private `.venv`.
- Evidence: 21 assistant focused backend tests, 226 broader backend tests (migration/PostgreSQL cases excluded), 70 frontend tests, TypeScript check, Vite build, one mocked assistant Playwright flow, and one post-integration core HTTP/Playwright stub journey all passed. Detailed evidence and scope are in `docs/TEST-EVIDENCE.md`.
- All assistant integrations are disabled by default. No Gemini, Gnani, Gmail, Calendar, or Twilio request was made. Approval semantics, retention enforcement, OAuth rate limiting, and key rotation require further review before enabling communication providers.
- Temporary RC services on ports 8022/5193 were stopped after tests. The original Phase B services remain intact. SQLite and test artifacts are preserved; no PostgreSQL/database state was changed.

## INT-02 architecture map and INT-19 asset recheck — 2026-11-09

- Added `docs/ARCHITECTURE-MAP.md` from the RC source, generated FastAPI OpenAPI, frontend route/auth/proxy inspection, SQLAlchemy model and Alembic graph inspection, and server-side provider configuration names. It distinguishes UI previews/static health from the real student flow and records explicit authorization and runtime gaps.
- OpenAPI was initially generated in-process using a read-only INT-17 `PYTHONPATH` package reference because the RC venv lacked `cryptography` at that checkpoint. A later verified install made standalone RC import succeed; see the standalone-runtime verification below. No DB connection or provider call occurred during schema generation.
- Read-only filename scan across every registered worktree found no `.glb`, `.gltf`, `.vrm`, `.fbx`, or `.obj` teacher/model asset. No files were opened or changed by the scan. INT-19/28 remain blocked on a rights-cleared suitable asset.

## INT-03/04/20 voice readiness recheck — 2026-11-09

- ADV-06 HEAD `d426fc1719a316098f2507eaf84862450d13512e` is already an ancestor of the INT-18B baseline; the diff from ADV-06 HEAD to the baseline is empty. No duplicate voice code was ported. INT-20 remains the voice checkpoint/interruption candidate adaptation.
- Presence-only inspection found non-placeholder Gnani key and endpoint settings in original-project POC-01/POC-02 `.env` files. The RC/recovery POC configs and process environment do not contain Gnani settings. Values were never shown, copied, or validated. No Gnani calls were made because none were approved.
- Offline regression: POC-01 8 passed (after rerunning from its documented module directory), POC-02 14 passed, POC-06 44 passed. The initial POC-01 root invocation failed collection only due to its relative import convention.
- Historical POC-02 live English/Telugu outputs remain present and their WAV headers verify mono 48 kHz/16-bit PCM. No playback judgment or new provider request was made. Live Prisma acceptance remains absent; live TTS acceptance is historical only.

## Registered worktree status refresh — 2026-11-09

Read-only `git worktree list --porcelain` plus per-worktree `git status --porcelain` was rerun. Porcelain entry counts below include untracked directories collapsed by Git; they are not file counts. The RC's uncommitted integration files/artifacts are expected and preserved.

| Worktree | Branch | HEAD (short) | Porcelain entries |
|---|---|---:|---:|
| `BHASHALEARN-AI` | `feature/int-05-adaptive-learning` | `e542103` | 2 |
| `BHASHALEARN-CLASSROOM` | `feature/unified-ai-classroom` | `70154c7` | 5 |
| `BHASHALEARN-INT13` | `feature/int-13-adaptive-quizzes` | `9bbeed8` | 9 |
| `BHASHALEARN-INT16` | `feature/int-16-teaching-intelligence` | `3aaaaa3` | 2 |
| `BHASHALEARN-INT17` | `feature/int-17-personal-assistant` | `028bb27` | 6 |
| `BHASHALEARN-INT18B` | `feature/int-18b-unified-integration` | `4d364d4` | 5 |
| `BHASHALEARN-INT21` | `feature/int-21-career-roadmap` | `3701823` | 6 |
| `BHASHALEARN-INT25` | `feature/int-25-communication-orchestration` | `70154c7` | 1 |
| `BHASHALEARN-INT26` | `feature/int-26-holoos-polish` | `70154c7` | 18 |
| `BHASHALEARN-INT26/_integration_rc_20261109` | `integration/release-candidate-20261109` | `4d364d4` | 93 |
| `BHASHALEARN-INT26/_phaseb_int18b_test` | `recovery/phase-1-student-journey-test` | `4d364d4` | 6 |

All other currently registered worktrees had zero porcelain entries. No changes were made outside the RC. Full filenames for the intentionally dirty INT-26/RC and preserved test-artifact worktrees are listed in the live `git status` output, not copied or altered here.

## Feature-tip lineage against INT-18B — 2026-11-09

The following are read-only `git merge-base --is-ancestor` checks and three-dot changed-path counts (`baseline...tip`, so the feature-side delta is measured from the merge base). This avoids treating later INT-18B files as deletions from branches that point to earlier ancestors.

| Branch tips | Relation to INT-18B baseline | Feature-side changed paths | Integration interpretation |
|---|---|---:|---|
| ADV-01 through ADV-07 | Tip is an ancestor | 0 each | Their committed tips are already in the baseline. Feature acceptance may still be incomplete. |
| CLASSROOM, INT-05-REMOTE, INT-09 through INT-16, INT-25, INT-26 branch tip | Tip is an ancestor | 0 each | Committed tip is already in baseline. INT-26's uncommitted work is separate and preserved. |
| INT-17 | Diverged at shared ancestor | 19 | Assistant-focused branch delta; selectively ported. |
| INT-19 | Diverged at shared ancestor | 5 | Procedural holographic-teacher prototype; not integrated as a realistic model. |
| INT-20 | Diverged at shared ancestor | 12 | Voice-state/interruption changes; adapted in RC. |
| INT-21 | Diverged at shared ancestor | 15 | Career roadmap changes; adapted in RC. |
| INT-22 | Diverged at shared ancestor | 8 | Command-center UI changes; adapted in RC. |
| INT-23 | Diverged at shared ancestor | 15 | Knowledge Studio changes; adapted in RC. |
| INT-24 | Diverged at shared ancestor | 16 | Research agent changes; adapted in RC. |

All enumerated non-ancestor deltas are still uncommitted in the RC rather than merged or cherry-picked. Adapted candidate code remains subject to the documented database, provider, security, and browser acceptance gates.

## INT-07 database readiness endpoint — 2026-11-09

- Added `/ready` and `/api/v1/ready` to the RC. They issue only `SELECT 1` through the configured engine and return a generic HTTP 503 message if DB readiness fails; driver details and connection strings are not returned. Existing `/health` liveness responses remain unchanged.
- Added HTTP coverage for both ready paths and a simulated connection failure. Focused `test_main.py` passed 6/6; the full isolated backend regression passed 228/228 with DB URLs blank and PostgreSQL/migration suites excluded. In-memory SQLite was used only in the focused readiness success test.
- No PostgreSQL connection, migration, DB write, provider request, or external service call was made for this change. Verify the endpoint against the exact authorized PostgreSQL test target after its local credentials are corrected.
- Real HTTP smoke on verified-free port 8022 returned 200 at `/health`, `/ready`, and `/api/v1/ready` with process-only random JWT secret, blank provider credentials, and in-memory SQLite. The server was stopped and 8022 rechecked free; original recovery 8016/5188 and PostgreSQL listener 55432 remain available.

## Standalone RC dependency and browser acceptance — 2026-11-09

- Retrieved `cryptography 46.0.7`'s CPython ABI3 Windows wheel directly from official PyPI. Its SHA-256 matched PyPI release metadata (`397655da831414d165029da9bc483bed2fe0e75dde6a1523ec2fe63f3c46046b`); installed the wheel with `--no-deps` into the RC `.venv` only. No other worktree or global Python changed.
- Without a `PYTHONPATH` overlay, RC app import and OpenAPI generation succeeded. `test_main.py` passed 6/6; broad backend regression passed 228/228 (one Starlette/httpx warning), with DB URLs blank and PostgreSQL/migration test files excluded.
- A fresh SQLite-backed test-only RC backend on 8022 and Vite on 5193 passed the full core Playwright student journey 1/1. HTTP asserted registration 201, login/auth-me/chat 200, invalid login 401; the test asserted no Gemini/Gnani host requests. Read-only DB counts were one student, one session, two messages, one labeled stub response; integrity `ok`.
- The temporary processes were stopped; 8022/5193 are free. Original Phase B 8016/5188 and PostgreSQL listener 55432 remain live. No PostgreSQL connection/migration, live provider call, or external communication was made.

## Authorized database config recheck — 2026-11-09

- Scanned only the registered BHASHALEARN worktrees' root/backend `.env` and `.env.local` files for a connection string matching the previously authorized host `127.0.0.1`, port `55432`, and database `bhashalearn_phaseb_e2e_96ce964941`. No matching local config was found. The existing recovery config still points at a different database and its credentials previously failed a read-only connection attempt to the authorized target.
- No credentials or connection URLs were printed. No config was edited, and no database other than the authorized target was accessed. The owner must enter the correct app-role DSN locally before PostgreSQL acceptance can continue.
