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

## Quiz analytics integration

The analytics response also summarizes INT-13 quizzes from answered quiz questions in the same authenticated student's assessment-attempt rows. It reports completed quizzes, answered question count, and mean score across completed quizzes for the selected UTC window. Groups with missing or duplicate positions, unanswered items, or no quiz metadata are excluded. Legacy objective practice is not mistaken for a quiz. INT-13 evidence already updates the shared topic progress counters, so mastery and recommendations include those submitted answers.

`backend.app.services.quiz_analytics` retains a provider-neutral contract for a future quiz source stored outside the current assessment-attempt table. Any such adapter must verify ownership, deduplicate by a stable attempt key, reject incomplete or invalid scores, and preserve source completion time.

## Schema and migration

No schema change was needed. INT-14 reuses migrations through 0010_mission_completions; no new migration is created.
