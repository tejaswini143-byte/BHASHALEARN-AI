# Feature 5 — Phase 1: Realistic 3D Teacher foundation

Status: In progress. This document records an inspected code baseline, not a release sign-off.

## Existing implementation (preserve)

- `frontend/src/TeacherPreview.tsx`: React Three Fiber scene, GLTF loading, animation mixer, humanoid bone fallback, expressions and viseme morph targets.
- `frontend/src/ImmersiveClassroom.tsx`: authenticated immersive classroom, 3D renderer fallback, voice-state bridge, lesson board and camera presets.
- `frontend/src/teacherCore.ts`: validated teacher actions, motion states, expressions, normalized board targets and viseme timeline.
- `frontend/src/immersiveVoiceBridge.ts`: subscription interface for voice state and audio-clock frames.
- `frontend/src/VoiceTutor.tsx`: existing speech playback, voice diagnostics and avatar synchronization.
- `frontend/tests/teacher.test.mjs`: teacher contract tests.

## Phase 1 change

Viseme timelines now reject overlapping intervals and unsafe integer end times; focused regression cases cover invalid overlap, unsafe bounds and adjacent valid intervals. Existing audio/teacher APIs were not replaced.

## Acceptance gates still open

1. Execute `cd frontend && npm ci && npm test && npm run build` in a clean checkout and record the output.
2. Verify voice bridge lifecycle, stale-generation handling and interruption/resume tests.
3. Confirm backend avatar event contract is necessary before adding endpoints; avoid creating redundant APIs.
4. Run a real-browser teacher and immersive classroom smoke test; verify WebGL fallback and console cleanliness.
5. Verify licensed, rigged model asset before claiming realistic human animation.

Do not mark Phase 1 complete until focused tests and build pass. Do not merge this branch into main without review.
