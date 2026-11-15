# Feature 4 — Phase 1: visual lesson architecture and audit

## Existing implementation (preserved)
- `VisualLessons.tsx` renders three WebGL simulations: solar system, geometry and pendulum, with a text fallback.
- `visualLessonsModel.ts` contains Telugu/English teaching copy, numerical simulation models and visual control state.
- `InteractiveLessonStudio.tsx` and `lessonEngine.ts` provide smartboard authoring, playback and exercises.
- `ImmersiveClassroom.tsx` and Feature 5 provide the rigged teacher and shared voice playback bridge.
- `App.tsx` already lazily loads the visual lesson route.

## Phase 1 change
- Add `visualLessonContract.ts` as a versioned and strictly bilingual visual lesson envelope.
- Enforce that the requested simulation scene matches the lesson id and every step has English/Telugu content.
- Add automated regression tests for valid existing lessons and malformed envelopes.

## Boundaries and follow-on phases
- Phase 2: improve simulation controls, visuals, fallback and accessibility; preserve existing math tests.
- Phase 3: backend lesson API and validation; never trust generated lesson plans without validation.
- Phase 4: connect visual scene, smartboard, teacher voice, progress and bilingual session context.
- Phase 5: browser E2E, backend tests, performance, security, CI and manual acceptance.

## Open risks
- Current lesson catalog is hardcoded, not generated dynamically from the backend.
- The visual simulation catalog and smartboard lesson plan use different schemas; conversion needs an explicit adapter.
- WebGL performance and device coverage need manual verification.
- Live GNANI synchronized teaching is not yet demonstrated end-to-end.
- These tests have been committed but have not been executed in this environment.
