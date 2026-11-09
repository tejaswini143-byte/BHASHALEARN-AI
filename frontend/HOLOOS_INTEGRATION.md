# HoloOS dashboard integration

This branch is based on integration candidate `4d364d4746ff97356cf26bfefda09903b243831d`. It retains the candidate's dashboard and visual system, and exposes the immersive classroom, Future Me, and learning memories destinations from the HoloOS sidebar.

## CODEX 1 handoff

1. Cherry-pick the `parallel/holoos-ux` tip onto the matching integration candidate.
2. Keep `frontend/src/Dashboard.tsx` as the single dashboard implementation. It remains exported through `AuthPages.tsx` and uses the existing `/dashboard` route, auth helpers, and API paths.
3. Include `frontend/src/dashboard.css`, `frontend/src/holoosDashboardModel.ts`, and the HoloOS tests with the dashboard update. No `App.tsx`, auth/API configuration, or backend changes are needed.
4. If the candidate advanced after this branch was cut, resolve dashboard conflicts by retaining the current integrated INT-22/INT-26 links and session/progress behavior, then applying the mobile keyboard controls and accessible loading, error, and progress semantics from this branch. Do not mount a second dashboard shell.

Verification commands from `frontend/`:

```powershell
npm test
npm run build
$env:BHASHALEARN_E2E_START_SERVERS = "1"
$env:BHASHALEARN_E2E_MOCK_API = "1"
npm run test:e2e -- holoos-dashboard.spec.ts
```
