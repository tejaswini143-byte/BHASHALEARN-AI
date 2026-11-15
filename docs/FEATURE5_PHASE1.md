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

Viseme and phoneme timelines now reject overlapping intervals and unsafe integer end times. Invalid begin() inputs are validated before changing the active avatar playback generation; unsupported language values are rejected. Regression tests cover invalid overlap, valid adjacent frames, preservation of active playback on bad input, and interruption silencing. Existing audio/teacher APIs were not replaced.

## Acceptance gates still open

1. Execute `cd frontend && npm ci && npm test && npm run build` in a clean checkout and record the output.
2. Verify voice bridge lifecycle, stale-generation handling and interruption/resume tests.
3. Confirm backend avatar event contract is necessary before adding endpoints; avoid creating redundant APIs.
4. Run a real-browser teacher and immersive classroom smoke test; verify WebGL fallback and console cleanliness.
5. Verify licensed, rigged model asset before claiming realistic human animation.

Do not mark Phase 1 complete until focused tests and build pass. Do not merge this branch into main without review.

## Execution environment note (2026-11-13)

The GitHub-connected branch was updated and read back, but the isolated execution container could not clone GitHub because DNS resolution of github.com failed. Therefore the current commit has **not** passed a fresh npm test/build or live browser test in this environment. Historical release-candidate tests do not certify these new changes. Phase 1 remains blocked on a runnable checkout/CI result; do not claim it complete.

## Manual-tester findings and fixes

- **Blank teacher in immersive classroom:** `ImmersiveTeacher` currently receives `model={null}` and renders no avatar. The page now explicitly discloses that no 3D teacher is loaded, instead of implying the character is visible. This is a truthful interim accessibility fix, not a working immersive 3D avatar.
- **Static GLB misrepresented as a human teacher:** the preview previously accepted non-skinned models. It now rejects non-rigged GLB files with a readable explanation and allows the learner to reselect a file.
- **Speech timing corruption:** overlapping viseme/phoneme cues and invalid language inputs are rejected before replacing the active playback session.
- **Dependency/test environment:** `react` and `typescript` are already declared in package.json and package-lock.json. The reported Windows failures are module-resolution/install failures, not proof of 18 application regressions. A clean-install GitHub Actions workflow was added at `.github/workflows/feature5-phase1.yml` using Node 22; no passing run has yet been observed.

## Still required for completion

1. Verify the CI workflow is enabled and finishes green, or provide the actual `npm ci` failure output from the Windows checkout.
2. Run browser/manual acceptance for avatar import (valid rigged, static, corrupt, oversized), keyboard/fullscreen, voice interruption, WebGL disabled, mobile and reduced motion.
3. Supply and validate a rights-cleared rigged avatar asset; the immersive scene still has no connected human model.
