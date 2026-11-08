# INT-14 Student Progress Analytics

The authenticated endpoint is GET /api/v1/analytics?range_days=7|30|90. Its only student selector is the authenticated bearer token. Current sources are owned learning sessions, completed objective assessment attempts, recorded learning_progress, and unique mission_completions. It does not read chat messages or student memory text.

## Calculation rules

- All activity dates and streaks use UTC calendar dates. A selected date window includes today and the preceding range_days - 1 dates, and ends at the next UTC midnight.
- A completed activity is one answered objective assessment attempt or one unique mission claim. Issued but unanswered attempts are excluded. Assessment rows and mission claims remain separately visible in trends and the timeline.
- Mastery is scored correct answers divided by scored attempts in the existing learning_progress evidence counters. Ambiguous and unanswered attempts do not enter the denominator. Strengths require at least three scored answers; improvement areas use scored topics.
- Mission XP is summed from the unique (student_id, mission_id) completion ledger, using the existing 100 XP level step and badge thresholds.
- The streak counts distinct UTC dates with a session start, answered assessment, or mission claim. It continues through today, or through yesterday if there is no event today. The response marks the streak as a lower bound if the bounded 370-day lookback is fully occupied.
- Study time is unavailable because the current schema records session start timestamps but no session end or trusted duration.
- Free-text topics without a recognized mapping are grouped under Other; the mapping currently recognizes equivalent fractions, Dijkstra shortest path, and common language topic terms.

## Future quiz analytics seam

backend.app.services.quiz_analytics contains a provider-neutral QuizAnalyticsProvider protocol and QuizAttemptEvidence value type. A future adapter may read its own completed quiz results and return deduplicated, student-authorized attempts for the requested time window. The adapter must verify ownership, bound the result set, deduplicate by its stable attempt_key, reject incomplete or invalid scores, and preserve the source completion timestamp. The analytics layer can then combine the returned score and maximum score with the matching subject/topic evidence. No INT-13 module, migration, API, or table is assumed or imported today; current dashboard metrics work without that provider.

## Schema and migration

No schema change was needed. INT-14 reuses migrations through 0010_mission_completions; no new migration is created.
