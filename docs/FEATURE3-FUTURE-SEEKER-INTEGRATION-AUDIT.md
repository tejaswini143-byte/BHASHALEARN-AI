# Feature 3 Future Seeker integration audit

## Baseline and branch review

- PR #3 remains a draft on `feature/feature3-future-seeker`, based on release candidate `integration/release-candidate-20261109` (`17eeee5a`).
- The PR head already implements authenticated career goals, skill self-reporting, deterministic prerequisite-aware roadmaps, curated resources, objective assessment evidence, bilingual Gemini gap analysis, weekly study tracking, roadmap snapshots, and a reused React dashboard route.
- The later `feature/feature3-phase1-*`, `phase2-*`, and `phase3-*` tips contain Feature 3 contract and saved-reflection work alongside unrelated Feature 1/4/5 commits. Their phase 2 migration also claims Alembic revision `0020`, which conflicts with PR #3's existing `0020_feature3_future_seeker`. Do not merge those branch tips wholesale; reconcile any desired reflection work with a new migration revision after the established head.

## Reference review

- EduPath documents a FastAPI service boundary, resume extraction, assessments, graph roadmaps, and context-aware mentoring. BHASHALEARN keeps its existing authenticated API, database, Gemini abstraction, and dashboard rather than adopting EduPath's separate Ollama/MongoDB/Pinecone stack. The repo landing page did not advertise a license file, so no source was copied.
- SkillBridge describes explainable skill gap readiness and learning paths and publishes an MIT license. Its product flow informed the explainable, evidence-labelled skill gap design; no source was copied.
- `nilbuild/developer-roadmap` demonstrates interactive roadmap nodes. Its current repository license reserves reuse rights, so only the general node/prerequisite interaction pattern is referenced; roadmap text, diagrams, and assets are not copied.

## Integration update

- Added an authenticated, student-owned Gemini mentor endpoint. It passes the saved career goal, self-reported skills, current roadmap phase completion, progress, and weekly study adjustment to the existing provider abstraction.
- Added an optional experience summary to the saved profile through migration `0021_feature3_experience_profile`, and an evidence-weighted learning-readiness score with per-skill points and an explicit note that it does not predict employability.
- Added English, Telugu, and mixed-language mentor controls to the existing Career Roadmap page. Conversation content is not persisted; the answer is generated on request using current saved context.
- Added backend service/API coverage and a mocked browser acceptance step for post-progress mentor context.

## Verification limits for this update

- Frontend unit tests: 96 passed.
- Frontend production build: passed (existing large-chunk advisory remains).
- `git diff --check`: passed.
- Local backend and migration tests could not run because this Windows environment has no Python executable.
- Mocked Playwright E2E was attempted but Vite failed to start after dependency installation withheld the `esbuild` install script; the browser could not connect. No real Gemini call was made.

## Additional reference file and license audit

- `Advitya07/edupath`: the repository root does not include a license grant. Its `backend/` and `frontend/` source files are therefore not copied or adapted. Resume parsing, skill diagnosis, phase planning, and mentor context are independently implemented against BHASHALEARN APIs and models.
- `prithvifr/SkillBridge`: the repository includes an MIT license. Files such as `components/StepAnalysis.tsx`, `types.ts`, and `services/geminiService.ts` may legally be reused with the MIT notice preserved. They depend on SkillBridge's Firebase configuration, app-specific service layer, and chart/data types, so no source files from it are included. Its readiness explanation and personalized gap flow are reimplemented with BHASHALEARN's PostgreSQL profile, evidence model, and Gemini service.
- `nilbuild/developer-roadmap`: the repository license reserves commercial and redistribution rights to its owners. No roadmap text, diagrams, data, or assets are copied. Only the general prerequisite graph interaction is used as design reference.
- The `@xyflow/react` MIT-licensed package is a new third-party dependency; it is not copied from any of the reference repositories.

## Additional integration work

- Added private-library PDF/DOCX resume upload, format-specific extraction, explicit consent before Gemini analysis, a skill suggestion review step, and persistence of confirmed skills and experience to the existing student skill profile and career goal. Migration `0022_feature3_resume_profile` stores the reviewed/extracted profile status alongside the existing goal.
- Added a React Flow graph over persisted roadmap phases with skill nodes, prerequisite arrows, completion styling, and node-to-phase navigation.
- Existing contextual mentor data includes the reviewed resume profile in addition to skills, goal, assessment/readiness, roadmap, and progress. Existing objective assessment and weekly adaptation continue to use the same student-owned profile and roadmap data.
- This phase still needs Gnani voice contextual routing, browser acceptance coverage for resume review and the graph, and backend/migration verification. Live provider tests require configured Gemini/Gnani credentials.
