# INT-05 — Adaptive Learning & Evidence-backed Memory

## Scope
INT-05 adds server-issued objective practice, deterministic adaptation, evidence-backed topic mastery, and bounded student-owned learning context across BHASHALEARN tutor experiences.

## Evidence rules
- Only an answer submitted to an assessment attempt issued by the backend can change mastery.
- Chat messages, voice transcripts, audio playback, visual lesson navigation, and client-provided progress values never change mastery.
- A response that does not match an issued option is stored as ambiguous and increments only the ambiguous counter.
- Existing mastery values are retained for audit continuity but marked `legacy_unvalidated`; they are not shown as assessed scores.
- Unsupported topics return 422 and remain unassessed.

## Supported deterministic assessment bank
- Equivalent fractions
- Dijkstra shortest path (including the built-in Dijkstra lesson title alias)

The question bank is intentionally explicit. It does not claim to assess arbitrary free-form topics. Expand it only with reviewed questions, answer keys, and tests.

## API
- `POST /api/v1/assessments/sessions/{session_id}/issue` — issues a server-owned question for an owned session.
- `POST /api/v1/assessments/{attempt_id}/answer` — scores an answer once; identical retries return the stored result and conflicting retries return 409.
- `GET /api/v1/progress` — lists the authenticated student's evidence-backed topic progress.
- `GET /api/v1/progress/{topic}` — returns normalized topic progress.
- Direct client writes to `/progress` are no longer supported.

Assessment responses never expose the expected answer before submission. Assessment attempts and progress are scoped to the authenticated student and session owner.

## Adaptation policy
Mastery is the percentage of recognized correct answers among recognized scored answers. Ambiguous submissions do not enter the denominator. The deterministic policy chooses diagnostic, guided, prerequisite, misconception-review, or challenge strategies based on the available evidence. This is a transparent baseline policy, not a trained student model.

## Integration
- Classroom, Advanced Chat, and Voice Tutor share the same objective practice component.
- Tutor instructions receive a bounded summary of assessed evidence and up to three recent saved notes for the current normalized topic.
- Visual Studio reads progress and displays guidance only; it cannot write mastery.
- Dashboard averages only topics with scored evidence and labels unassessed topics accordingly.

## Migration
Revision `0006_adaptive_learning_memory` follows `0005_session_visual_state`. Legacy progress rows receive normalized topic keys and `legacy_unvalidated` status. Existing legacy score/attempt values are retained but are not treated as evidence. Downgrade removes the new columns and attempt table; assessment attempts and evidence counters created after upgrade are lost on downgrade.

## Verification status
The repository branch includes backend and frontend tests for the assessment flow. Tests, migration upgrade/downgrade, production build, PostgreSQL concurrency, and live Gemini/voice acceptance must run in a Python/Node environment before production sign-off. Do not mark INT-05 fully verified until those checks pass.
