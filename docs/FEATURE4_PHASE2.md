# Feature 4 — Phase 2: Interactive simulation reliability

## Existing UI retained
Solar-system selection and time scale, geometry size and rotation, pendulum length/gravity and play/pause, bilingual instructions, WebGL fallback and reduced-motion handling.

## Changes
- Make the reset callback stable and declare it in the keyboard effect dependencies.
- Reset pendulum clock **and** visible pivot angle, preventing a paused simulation from retaining an old pose after reset.
- Add source-level regression checks for both fixes.

## Manual QA
1. Open Visual Lessons and choose Pendulum.
2. Play until the bob swings away from center; pause; reset. The bob should return to the vertical resting pose.
3. Repeat reset with the R shortcut outside text inputs and verify no stale controls.
4. Change to Solar System and Geometry; check sliders and keyboard lesson-step navigation.
5. Switch English/Telugu, enable reduced motion, and verify controls remain operable.
6. Verify WebGL fallback on a browser without 3D support.

## Pending
- Run frontend tests and production build in the user's Windows checkout.
- Browser tests with authenticated session and real WebGL.
- Further visual polish and full Phase 2 acceptance.
