# Feature 3 — Future Seeker — Phase 1

## Existing functionality audited
- `/future-me` renders four deterministic, clearly illustrative career scenarios, with choices and reflective skills.
- `/career` is an authenticated career planner backed by student-owned career goals, skill self-assessments, roadmaps, lessons and quizzes.
- These are **different** experiences; neither scenario choices nor the simulation should be represented as a prediction, verified qualification, hiring decision, or assessment.

## Phase 1 scope
1. Establish a versioned, allowlisted contract for a future handoff between local reflection and career planning.
2. Validate untrusted input, enforce bounded data, deduplicate reflective skills.
3. Preserve provenance as `illustrative-simulation`; no automatic writes to student profiles or career goals.
4. Document frontend and backend boundaries before implementing persistent or AI-driven features.

## Later phases / acceptance gates
- Phase 2: authenticated backend ownership and persistence with migrations and tests.
- Phase 3: accessible, bilingual integrated Future Seeker experience and explicit consent for saving reflections.
- Phase 4: connect learning plans and voice/teacher sessions without conflating reflections with verified skills.
- Phase 5: end-to-end browser, security, accessibility, CI and regression gates.

## Verification
Run `npm test` and `npm run build` from `frontend`; run the backend regression suite before merging. GitHub connector writes do not execute these tests. No provider credentials are needed for this phase.
