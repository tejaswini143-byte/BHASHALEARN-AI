# BHASHALEARN final release integration manifest

This branch is an isolated integration checkout. Feature source checkouts and their existing staged, unstaged, and untracked files are preserved.

## Base and intended sources

| Track | Source | Base / status | Integration handling |
|---|---|---|---|
| Release base | `origin/integration/release-candidate-20261109` at `17eeee5a3bf3ab319479d0dc777d0743f6d2340a` | Shared base of PR #2 and PR #3 | Starting point for this branch |
| Feature 1 | `origin/fix/feature1-voice-diagnostics-ci-20261113` at `15534247478644120eca83f7fc00d77e612e949f` | PR #2 targets the release base; open draft | Merge after the Feature 2 port so overlapping assistant/voice files can be reconciled here |
| Feature 2 | `C:\Users\Tejaswini\BHASHALEARN-FEATURE2-INTEGRATION` at `17eeee5` plus 18 staged files | PR #6 head `336d99b` targets `main` and is a standalone app. The staged worktree changes are an integration port on the release base. | The staged port was copied into this checkout; source staging remains untouched. Review, test, and commit on this branch. Do not merge PR #6 wholesale. |
| Feature 3 | `feature/feature3-future-seeker` at `b04bd0bffcc9340a555e3e7c8c0fadcde8f77bde` | PR #3 targets the release base; open draft | Merge after core and Feature 2; inspect later reflection worktrees before finalizing. |
| Feature 4 | `feature/feature4-phase4-visual-api-integration-20261113` at `ba197489cdd87b938dad73153ce73245677b9fb0` | PR #7 targets its phase 1 branch, not the release base; open draft | Merge its full phase history and resolve release-base conflicts here. |
| Feature 5 | `feature/feature5-talkinghead-integration` at `a7e17444d6c28e824889e1f0e80218118ad3d71b` | PR #8 targets older Feature 1 commit `191b324`; open draft | Merge after current Feature 1 to retain current desktop/voice fixes and VRM work. |

## Preserved local state

- Feature 1 acceptance checkout keeps its user edit to `scripts/desktop_companion.py` (port `18028`) and untracked `.vite/` directory. Neither is part of the integration source port.
- Feature 2 integration checkout retains its 18 staged files unchanged after copying their staged diff.
- Feature 3 and Feature 5 checkouts were clean at inspection; their branches remain untouched.
- `BHASHALEARN-INT26` contains unrelated untracked worktrees and test artifacts; they remain untouched. Its branch is not a substitute for the release-base feature PRs.
- The supplied screenshot is stored at `docs/design-reference/bhashalearn-15-screens.png`. No repository copy existed before this integration task.

## Migration plan

The release base's current migration head is `0019_explicit_call_microphone_auth`.

- Feature 2 integration port adds `0020_assistant_livekit_sessions` from `0019`.
- Feature 3 adds `0020_feature3_future_seeker` from `0019`, then `0021_feature3_experience_profile`, then `0022_feature3_resume_profile`.
- Feature 4 adds `0020_visual_lesson_session_state` from `0019`.

These are parallel Alembic heads. After all relevant feature migrations are integrated, add a no-op merge revision with all retained heads in `down_revision`, then verify upgrade/downgrade/re-upgrade on a disposable database. Do not renumber or rewrite released migration identifiers.

## Integration validation gates

Pending: resolve cross-feature conflicts; confirm routers are included once; run Alembic graph checks and migration tests; run backend and frontend tests/build; run browser routes and responsive checks; report unavailable live providers/Windows actions as blocked rather than passed. No PR is merged by this work.
