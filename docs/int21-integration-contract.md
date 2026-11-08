# INT-21 integration contract

## Provider and feature seams

- **INT13 quizzes:** roadmap assessments may be opened through the authenticated quiz API using `{topic, difficulty, language, question_count}`. A quiz adapter should return the attempt IDs, topic, score, and completion time. Roadmap code must never trust a client supplied score; it should consume only server graded, student-owned attempt evidence. INT13 stores quiz metadata in assessment attempt records, so the future adapter should deduplicate quiz results by quiz/attempt ID.
- **INT14 analytics:** a future `QuizAnalyticsProvider.completed_attempts(student_id, start_at, end_at, limit)` can expose completed attempts as `QuizAttemptEvidence(attempt_key, student_id, subject, topic, completed_at, score, max_score)`. Keep analytics optional and bounded; only whole-number, finite, in-range scores count as evidence. INT-21 currently reads existing `LearningProgress` objective evidence and does not import INT14.
- **INT16 teaching intelligence:** phase cards can pass the current topic, difficulty, teaching language, strategy, and recent objective evidence into `TeachingEvidence` / `deterministic_plan`. Accept only validated `LessonPlan` output. Keep goal selection and prerequisite ordering authoritative in the roadmap service; INT-21 currently uses deterministic instructions and does not import INT16.
- **INT19 holographic teacher:** UI adapter input should be a selected phase's bounded lesson title, objective, language, and next activity; output can provide an optional visual/teacher session reference. It must not own student progress or mark a milestone complete.
- **INT20 multilingual voice:** voice adapter input should be phase text plus the selected `english`, `telugu`, or `mixed` language. Preserve skill and course terminology. Audio playback status is presentation state and must not be treated as learning evidence.

## Catalog and student data

`GET /api/v1/courses` and `GET /api/v1/courses/{course_id}/lessons` are the catalog source. Roadmap course and lesson IDs are emitted only when catalog titles match a taxonomy skill; `null` means no matching catalog content exists yet. Goal, skill profile, and milestone calls are scoped to the bearer-token student. Self-reported proficiency is not mastery evidence.

## Migration coordination with INT17

The verified source migration head was `0010_mission_completions`. INT-21 adds `0011_int21_career_roadmap` with `down_revision = 0010_mission_completions` and does not edit prior revisions. At inspection time the separate INT17 worktree had `0011_int17_assistant` followed by `0012_int17_provider_integrations`, also based on `0010_mission_completions`. These feature branches therefore intentionally have independent heads while developed in parallel.

When integration combines both branches, retain both feature migrations and add a merge revision with `down_revision = ("0011_int21_career_roadmap", "0012_int17_provider_integrations")`. Verify the combined graph with `alembic heads` and `alembic history`, then upgrade and downgrade disposable databases before applying anything to a shared environment. Do not renumber or edit either branch's migration files to resolve the graph.

## Current boundary

The roadmap planner is deterministic and provider-free. No employment-market feed, salary data, hiring guarantee, or live forecast is consumed. The bilingual roadmap summaries and milestone copy are generated locally; matched catalog lessons retain their original titles and technical terms.
