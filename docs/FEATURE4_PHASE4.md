# Feature 4 Phase 4 — Frontend ↔ backend visual lesson catalog (first integration slice)

This branch adds an authenticated client for GET /api/v1/visual-lessons, validates versioned bilingual scene envelopes, and hydrates the interactive React workspace with the backend catalog. It rejects unknown scenes, duplicate IDs, and invalid data. On network or schema errors it retains the built-in lessons and shows a status message. In-flight fetches are aborted on unmount.

**Not yet integrated:** 3D teacher lip-sync/voice, smartboard session synchronization, persistent learner progress, and end-to-end browser acceptance. Those remain Phase 4 follow-on work and Phase 5 gates; do not present this slice as full Phase 4 completion.

## Local checks
From the repository root:
```bat
cd frontend
npm test
npm run build
cd ..
"C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe" -m pytest -p no:cacheprovider -q backend/tests
```

Manual browser: sign in, open Visual Lessons, confirm backend-synchronized status; switch subjects and Telugu/English; test backend unavailable fallback; confirm expired token redirects via existing AuthGate; test solar system, geometry, and pendulum controls. Verify no credentials are logged.
