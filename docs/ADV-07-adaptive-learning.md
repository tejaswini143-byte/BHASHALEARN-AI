# ADV-07 Adaptive Learning and Student Memory

## Implemented

- `GET /api/v1/students/me/learning-profile` returns authenticated preferences,
  per-topic proficiency, up to ten recent scored outcomes, and topics marked for
  revision. Activity excludes prompts, submitted answers, feedback, and chat.
- Learning preferences support `telugu`, `english`, or `mixed` and a self-selected
  pace of `slow`, `steady`, or `fast`. Pace is descriptive context; it does not
  change the evidence thresholds.
- Assessment-backed adaptation is deterministic. Fewer than three scored
  responses stays beginner; from three responses, accuracy of at least 50%
  selects intermediate, and advanced requires at least five responses with
  95% accuracy. Two consecutive wrong answers request a
  hint, three request a worked-example review, and recent accuracy below 50%
  after at least 80% aggregate accuracy recommends revision. Ambiguous answers
  are excluded from scored outcomes.
- Adaptation responses expose the strategy, recommendation, and reason. The
  policy in `backend/app/services/adaptive_learning.py` is storage independent.
- Memory CRUD is scoped to the authenticated student. A student can correct a
  topic or note with `PATCH /api/v1/memories/{id}` and delete a memory. The API
  does not create memories from chat automatically; notes are bounded to 2,000
  characters and should be concise learning summaries rather than raw private
  conversations.
- Typed adapter protocols define future handoff seams for ADV-03 tutoring,
  ADV-04 smartboard rendering, and ADV-06 voice delivery. No new provider or
  modality integration is activated by these contracts.
- `lesson_directive(profile, topic)` resolves the preferred language, pace,
  topic difficulty, strategy, and recommendation into one provider-neutral
  directive. The shared session context also includes the selected pace.

## Data and privacy boundaries

Assessment attempts and manually supplied memories use the existing
student-owned database tables and authenticated ownership checks. The profile
API queries only the authenticated student's preferences, progress, and
assessments. Course title is used as a subject label only when an associated
session provides one. Without that association, `subject` is `null`; the
current catalog has no separate subject taxonomy.

Recent profile activity contains topic, correctness, and time only. Existing
assessment storage still holds the issued question and a submitted choice so
that grading and idempotent retries work; it does not store free-form tutor
conversation in learning memory. The existing session history remains a
separate feature with its own ownership and retention behavior.

The `0009_learning_pace` Alembic revision adds the preference column with a
`steady` default. ADV-02 already uses revision `0008_document_embeddings`, so
the required integration order is ADV-02 `0008_document_embeddings` first,
then ADV-07 `0009_learning_pace`. The ADV-02 migration is not present in this
worktree; the ADV-07 migration chain is intentionally incomplete until those
branches are integrated. This change has not been migrated in any database.
Deployments must apply the integrated migration chain in their own approved,
backed-up environment before using the persistent pace field.

## Limits and integration requirements

- Rules use small deterministic heuristics, not a validated learning-science
  model. They must not be used for grading, placement, or consequential
  decisions. Telugu and mixed-language teaching content still needs review.
- “Recent decline” means the last three scored objective answers are below 50%
  while the cumulative rate is at least 80%; this is a revision signal, not a
  statistically calibrated trend.
- The current question bank supports equivalent fractions and Dijkstra's
  shortest path only. Unsupported topics remain unassessed.
- ADV-03 should consume `AdaptiveLessonDirective` and the profile's bounded
  context, without persisting chat as memory. ADV-04 should render the directive
  and report activity through an explicit event contract. ADV-06 should respect
  the selected language and must not alter mastery from transcription alone.
- Any durable adapter must preserve student scoping, deletion behavior, and
  transaction-safe updates. The in-memory policy itself stores no learner data.

## Verification

The focused adaptive/profile/memory/auth/session-context suite passed with 38
tests. The broader backend suite passed with 101 tests when migration tests
were excluded, and the schema-only SQLite test passed separately. The
Alembic-upgrade test was checked against its temporary SQLite fixture and
stopped before DDL because ADV-02's `0008_document_embeddings` parent is not
present in this worktree. No persistent or shared database was migrated.
