# Feature 4 Phase 4 — Cross-mode handoff

The visual lesson workspace now offers explicit navigation to the immersive smartboard classroom and the existing voice tutor. The selected allowlisted visual scene ID is passed through a URL query parameter. The immersive classroom selects the corresponding sample lesson (geometry maps to the existing Pythagoras lesson) and resets playback when the selection changes. The voice tutor pre-fills the topic field from the visual lesson title; it does not automatically create a voice session or synthesize audio.

This is **navigation and lesson-context handoff**, not synchronized voice playback, teacher lipsync, or server-persisted progress. Those remain separate acceptance tasks. The immersive classroom's pendulum mapping is not available in the current smartboard catalog and defaults to its existing lesson rather than inventing a matching board scene.

## Local verification

Run `npm test` and `npm run build` inside `frontend`. Then sign in, open Visual Lessons, select Solar System, follow the 3D classroom link and verify the smartboard selects Solar System. Return, select Geometry and verify the Pythagoras board opens. Follow Voice Tutor and verify the topic is prefilled. Check navigation without a token redirects to login. Repeat with Telugu selected. Confirm no provider keys appear in the browser.

Backend regression previously reported by user: 379 passed, 3 skipped. Frontend acceptance for these new commits is not yet reported.
