# Feature 5 — Phase 5 QA and release checklist

## Automated gates
- Node 22: clean locked npm install, package verification, full frontend unit tests and TypeScript/Vite production build.
- Chromium smoke suite: isolated Vite server with mock-API mode, unauthenticated immersive route redirects to login and mobile login layout avoids horizontal overflow.
- Browser failure traces/screenshots are retained as GitHub Actions artifacts.
- Run these checks on this branch and pull requests that change frontend files. No CI pass has yet been observed.

## Manual test matrix (required before release)
1. Authentication: no token, expired token, offline backend, recovery from backend failure; do not leak user details.
2. Avatar: valid licensed skinned GLB, missing rig, corrupt GLB, >25 MB file, repeated upload of same file, replace, remove, WebGL failure, no avatar.
3. Voice: English/Telugu GNANI audio playback, pause/resume, interrupt, stop, replay, audio/network errors, no blendshapes, no audio cues. Verify mouth closes immediately on pause/interruption and does not reactivate from old frames.
4. Teaching: all sample lessons, previous/next/play/pause, keyboard shortcuts, board focus labels, exercise wrong/correct answers and reset when switching lessons.
5. Accessibility: keyboard-only, screen reader labels, error announcements, reduced motion, 375px viewport, desktop resizing.
6. Performance: repeat model load/unload, GPU memory, frame rate on a lower-end device, bundle loading and no browser console errors.
7. Security: upload is local only, no credentials in git, no production database used for E2E.

## Release criteria
- All required unit/build/CI browser gates green.
- Live GNANI and backend integration tested in an authorized environment.
- Valid realistic rigged avatar renders and visibly animates.
- No blocking browser/manual QA defects.
- Merge only after verifying upstream changes and integration branch compatibility.

**Status:** QA infrastructure added; automated CI and manual acceptance pending. No production-ready claim yet.
