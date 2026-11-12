# Release Readiness

**Status: NOT READY.**

## Latest verification snapshot — 2026-11-11

The following replaces the older provider and runtime status recorded in the historical audit below:

- Local frontend `http://127.0.0.1:15199` and backend `http://127.0.0.1:18027` returned HTTP 200; `/ready` confirmed the isolated SQLite database is ready.
- Real-browser student flows verified Gemini English/Telugu tutoring, Gnani Prisma STT and Timbre TTS, Gemini PDF embeddings/indexing and cited grounded answers, generated quizzes/scoring, courses/progress, and reusable learning memory.
- Backend suite: 252 passed, 3 skipped. Frontend: 82 passed. TypeScript, production build, and `git diff --check` passed. Vite still warns that the Three.js bundle exceeds 500 kB.
- The immersive route's nested `drei/Html` portals produced React unmount errors. Those lesson portals were replaced with an accessible lesson board; playback updated the board, and two classroom-exit checks produced no new browser errors.
- A synthetic RAG PDF remains in the isolated preview database because its browser deletion interaction timed out. It was not removed by direct database edits.

Current deployment gates remain: production database/migration acceptance, security and approval review, a rights-cleared rigged human model for realistic movement, dedicated verification of interrupt-and-resume during active audio, and the external features listed below. See [the local demo setup and limits](LOCAL-DEMO-SETUP.md).

## Historical gates (2026-11-09 audit)

- [x] Verified INT-18B baseline selected and isolated release-candidate worktree created.
- [x] Existing worktree changes and artifacts inventoried and preserved.
- [x] Static frontend/backend route, auth, persistence, migration, provider, and readiness boundaries mapped in `docs/ARCHITECTURE-MAP.md`; runtime/database acceptance remains separate.
- [x] Add sanitized `/ready` and `/api/v1/ready` DB probes, preserving static liveness routes; 6 isolated HTTP tests pass. Verify against the authorized PostgreSQL target remains open.
- [x] Rerun broad backend regression after readiness change: 228 passed, 0 failed, 1 warning; database URLs blank; PostgreSQL/migration test files excluded.
- [x] Resolve RC cryptography dependency using an official PyPI wheel whose SHA-256 matched published metadata; standalone RC import and the 228-test backend regression pass without a cross-worktree `PYTHONPATH`.
- [x] Run standalone RC core browser journey on fresh SQLite: 1/1 Playwright passed registration/login/dashboard/classroom/stub response/persistence/invalid login; read-only DB counts and integrity passed; no Gemini/Gnani requests observed.
- [x] Candidate regression gates: backend 206 passed/3 skipped, frontend 70 passed, build succeeded, and focused mocked INT-21/23/24 browser flows passed.
- [x] Run the selected mocked UI browser suite after integrating INT-21/23/24: 46 passed, 0 failed, 8 database-gated skips. Two direct HTTP checks requiring a test API process were excluded.
- [x] Rerun targeted INT-13/14/15/16 regressions: 51 SQLite-backed backend tests, 20 frontend tests, and 13 mocked Playwright browser cases passed.
- [x] Adapt INT-20 voice checkpoint/interruption support into the RC while preserving the INT-10C component and avatar bridge contracts; 209 backend tests/3 PostgreSQL-gated skips, 70 frontend unit tests, TypeScript, bundle, and the mocked resume browser flow passed.
- [x] Selectively port INT-17's 19-file assistant feature delta while preserving later INT-18B baseline files; 21 assistant tests, 70 frontend units, TypeScript/build, mocked assistant browser flow, and standalone real-HTTP SQLite student journey passed. Latest broad backend run passed 228/228 in the RC venv. No provider call or migration was made.
- [x] Re-run core real-HTTP/Playwright journey with console/network classification: 1/1 passed on fresh isolated SQLite, with only two restricted-network Google Fonts resource failures and the intentional invalid-login 401; no unexpected console errors, page exceptions, API 5xx, or provider requests. Read-only DB integrity/count check passed.
- [ ] Restore and read-only verify the exact authorized disposable database target and Alembic revision.
- [ ] Run full core HTTP and Playwright regression against the authorized PostgreSQL test database after exact-target credentials are restored; current standalone SQLite browser journey passes.
- [ ] Verify the single previously approved Gemini response (if key is valid and target remains authorized); no further provider calls without approval.
- [ ] Verify Gnani STT/TTS with explicit test budget and approved synthetic audio/text.
- [ ] Review and integrate later features one commit at a time with migration/API compatibility checks.
- [ ] Run feature-level browser/API/database acceptance, negative cases, reload persistence, mobile/accessibility, and console/network checks.
- [ ] Verify realistic licensed teacher asset and both shared-context appearance modes.
- [ ] Complete security, performance, recovery, documentation, and demo launch gates.
- [ ] Prepare rollback and reproducible launch instructions; deployment requires separate approval.

## Historical blockers from the 2026-11-09 audit

1. Recovery configuration/database mismatch: configured database `bhashalearn_phaseb_9991cde0ee` versus only authorized `bhashalearn_phaseb_e2e_96ce964941`; a read-only attempt to the authorized target with the configured credentials fails authentication.
2. `BHASHALEARN_GEMINI_API_KEY` is present in a local ignored config but validity is unconfirmed; no provider call was made. The one approved call is blocked until authenticated test data can be created against the authorized database.
3. No verified licensed realistic rigged avatar asset is established.
4. INT-26 has dirty frontend code and artifacts; the original worktree is preserved and its candidate adaptation still needs complete visual/functional acceptance.
5. INT-20 voice rate limiting currently uses process memory; this is suitable only as a local candidate guard and needs a shared limiter before multi-process production use.
6. RC migrations `0011`–`0015` are unapplied and have not been tested against the authorized PostgreSQL database. INT-17 communication approval, retention, key-rotation, and live side-effect controls also need security acceptance.

## Rollback

No integration source commits or database mutations have been made. To abandon this candidate later, retain its worktree until its contents are reviewed; do not remove it while `.python`, `.venv`, test evidence, or user artifacts remain. No automated rollback/deletion is authorized.
