# INT-05: Adaptive Teaching and Persistent Learning Memory

## Scope and architecture

INT-05 adds a small student-owned learning profile for objective evidence on the built-in Fractions and Dijkstra topics. Existing learning sessions, chat messages, Gemini tutoring, voice endpoints, visual lessons, and student preferences remain the sources of truth for their existing data. A new assessment-attempt table stores server-issued questions and submissions; `learning_progress` stores one normalized topic summary per student. The existing tutor retrieves only validated assessment evidence for the authenticated student and the active session topic.

The implementation does not score free-form chat, a Prisma transcript, TTS playback, or viewing/switching a visual lesson. Chat/Voice continue to use the same `/tutor/sessions/{session_id}/chat` route. Visual lessons show read-only adaptation guidance. The local Dijkstra quiz remains local and does not affect persisted progress.

## Evidence and assessment flow

`POST /api/v1/tutor/sessions/{session_id}/assessments` issues an objective check for a supported topic. The expected answer is server-side and omitted from the issue response. The current deterministic bank covers equivalent fractions and choosing the smallest directly connected Dijkstra edge. Unsupported topics return `422` without creating a progress row.

`POST /api/v1/tutor/sessions/{session_id}/assessments/{assessment_id}/answer` accepts A/B/C/D or `unsure`. Correct and incorrect answers are scored deterministically. `unsure` is recorded as ambiguous, with no mastery update. Repeating the same submission returns its stored result; submitting a different answer for an already completed assessment returns `409`.

Asking a question, claiming to understand, listening to an explanation, changing language, switching modes, or visiting a visual lesson does not update mastery. No LLM response is used as a correctness signal.

## Mastery and strategy policy

- A topic with zero scored evidence is `not_assessed`; it has no displayed score.
- First correct scored answer starts at 60%; first incorrect starts at 35%.
- Each subsequent correct answer adds 10 percentage points; each subsequent incorrect answer subtracts 12. Scores are clamped to 0–100.
- Ambiguous answers do not change score, counts, or streak.
- `demonstrated_proficiency` requires at least 85%, four scored checks, and three consecutive correct answers.
- Repeated recent mistakes or score below 35 recommend beginner prerequisite review. A recent misconception selects a targeted misconception review. Repeated evidence at 65% or higher recommends intermediate guided practice. Otherwise the system keeps scaffolding or uses the saved student learning level for a diagnostic.
- A single correct answer cannot mark proficiency.

The bank stores concise misconception codes such as `denominator_only`, `unequal_scaling`, `larger_edge`, and `not_connected`. The tutor receives only bounded, structured information for the current topic, including evidence counts, category, difficulty, strategy, and recent misconception labels. This data is delimited as learner-profile data, not instructions. Existing bounded visual context and chronological conversation history are retained.

## Persistence, ownership, and concurrency

Learning memory belongs to the authenticated student. Session endpoints verify ownership; the API never accepts a student ID for authorization. `learning_progress` has a unique `(student_id, topic_key)` constraint; normalization applies NFKC, case folding, and whitespace normalization. Assessment attempts link to student, session, and progress rows with cascading foreign keys.

Answer submission locks the attempt and progress rows with `SELECT ... FOR UPDATE` on PostgreSQL and updates evidence/result in one transaction. The attempt row is the idempotency key. The topic progress row serializes scoring for a topic. SQLite is used by deterministic tests but does not provide PostgreSQL's row-level locking semantics; production concurrency behavior must be verified against PostgreSQL.

Legacy client-written `PUT /api/v1/progress` is retained as a `405` response so clients cannot fabricate mastery. Authenticated read endpoints are `GET /api/v1/progress`, `GET /api/v1/progress/{topic}`, and `GET /api/v1/progress/summary`. Summary rows include sessions not yet assessed, with a null score and `not_assessed` category. Recent evidence omits expected answers.

Migration `0006_adaptive_learning_memory` adds normalized topic/evidence columns and creates `learning_assessment_attempts`. Existing progress rows are marked with zero validated evidence, so legacy caller-written percentages are not presented as demonstrated learning. Case/whitespace-equivalent legacy topic rows are consolidated under a normalized key, keeping the highest legacy score and maximum attempt count; those legacy values remain unvalidated and do not affect mastery category. Before consolidation, each removed duplicate is copied in full to `learning_progress_legacy_duplicates`. Downgrading to revision 0005 restores those rows and drops the archive table. Downgrading from 0006 also removes the new assessment-attempt table and its evidence, so create and verify a database backup before any downgrade. No migration should be run against production for this POC.

## Student-facing behavior

Chat and Voice offer the same objective practice card when the active topic is supported. The card reveals the answer only after submission and displays the feedback and resulting recommendation. The dashboard shows topic category, evidence count, recommended difficulty, strategy, and review hints. Unassessed topics are not represented as 0%. Visual Studio displays read-only guidance for the selected session topic; lesson selection and animation do not score evidence.

## Verification

The Windows CMD result supplied for the pre-fix revision was 68 backend tests passed and 7 failed, all at registration validation in `test_adaptive_learning.py`. The fixtures used the reserved `.test` domain while the production `EmailStr` schema rejects it. Those seven test addresses now use distinct `@example.com` values; production validation was not weakened. The current sandbox cannot rerun Python tests because `python` is not on PATH and the project virtual-environment launcher points to a missing Python 3.12 interpreter. The user-reported 66 Gnani POC passes are from the prior run, before this fixture change. The frontend build has been rerun successfully after the INT-05 frontend changes.

Migration `0006` has not been applied to the user's database. Its SQLite Alembic regression test now seeds two normalized-equivalent legacy progress rows, checks that one is archived and one kept after upgrade, then verifies both original rows are restored by downgrade. That test has not executed in this environment.

From the repository root:

```cmd
python -m pytest -q backend\tests\test_adaptive_learning.py backend\tests\test_progress.py backend\tests\test_database.py
python -m pytest -q backend\tests
set PYTHONPATH=%CD%\pocs\poc01_prisma_stt;%CD%\pocs\poc02_timbre_tts;%CD%\pocs\poc06_bilingual_voice;%CD%
python -m pytest -q pocs\poc01_prisma_stt\tests pocs\poc02_timbre_tts\tests pocs\poc06_bilingual_voice\tests
```

From `frontend\`:

```cmd
npm.cmd run build
```

## Manual acceptance

1. Open a new Fractions session and confirm the dashboard labels it not assessed.
2. Send normal Chat and Voice questions and verify evidence remains zero.
3. Issue practice, submit `unsure`, and verify score remains absent.
4. Submit an incorrect answer and inspect the recorded evidence and review strategy.
5. Retry the same assessment answer and confirm evidence does not increment twice.
6. Complete enough independent checks to confirm score and difficulty policy; verify one correct answer alone never gives demonstrated proficiency.
7. Open another session on the same topic and verify the tutor receives the same student's topic memory.
8. Switch between Chat, Voice, and Visual; verify same session, language, and history. Visual selection does not change evidence.
9. Sign in as another student and verify progress endpoints return only that student's records.

## Limitations

- Objective assessment generation currently supports only equivalent fractions and a small built-in Dijkstra graph. Other topics stay unassessed rather than receiving heuristic grading.
- Evidence is objective and deterministic; open-ended conceptual answers are not graded in this POC.
- Misconception phrases and assessment feedback are fixed-language templates; full natural localization of the progress interface can follow later.
- PostgreSQL migration and concurrent submission behavior require local database-backed verification; SQLite tests alone do not prove row-lock behavior.
- The migration's duplicate preservation and downgrade restore are covered by a disposable SQLite Alembic regression test; that test must be run in an available Python environment before migration use.
- Visual recommendations are read-only. Existing local visual quiz responses do not enter persistent learning evidence.
