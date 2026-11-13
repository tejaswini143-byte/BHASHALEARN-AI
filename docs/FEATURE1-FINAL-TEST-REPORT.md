# Feature 1 Final Test Report

Date: 2026-11-13 (Asia/Kolkata)
Repository: `C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109`
Branch: `integration/release-candidate-20261109`
Starting HEAD: `4fe57412596b3619941897246c1109686bd91e5b`
Delivery commit: recorded after final push verification

## Summary

**Status: LOCAL ACCEPTANCE REQUIRED.** Source repairs and regression checks are complete. A live Gemini planner request now returns a valid Notepad-and-type plan, but that plan was deliberately not executed. No actual speech sample was captured in this run, so there is no fresh Prisma transcript and no complete microphone-to-Windows command result. The latest available actual Prisma evidence remains the 2026-11-12 pair of captures: one incorrect transcript and one empty transcript.

## Root causes found and repairs

| Finding | Evidence | Repair/status |
|---|---|---|
| Low microphone signal and unreliable Prisma output | Prior measured capture RMS −45.9 dBFS, peak 1,029/32,767, 28.4% of frames above −45 dBFS; one earlier transcript was wrong, retry empty. | Added UI diagnostics for duration, RMS, peak, speech-level frames, clipping, WAV size and low-input hint. No gain is applied without a fresh recording; low input remains a hardware/setup acceptance item. |
| Gemini returned an unbound typing target for a newly opened Notepad | Fresh harmless Gemini request returned `open_app(notepad)` then `type_into` without a target; strict validation rejected it with 502. No Windows action occurred. | The one safe, explicit `open_app(notepad)` + unbound `type_into` + local dictation sentinel case now normalizes to guarded `type`. The executor still verifies Notepad foreground and a unique editable document. Other unbound targets remain rejected. Repeated live Gemini request returned the valid two-step plan. |
| Companion rejected the documented backend port | Runbook uses `127.0.0.1:18027`; companion loopback allowlist omitted 18027, causing `/background/enable` to reject it. | Added only loopback port 18027 to the allowlist. Regression coverage checks it is accepted and an unlisted port remains rejected. |
| Capture metrics were discarded | Voice Tutor used RMS only for VAD and exposed no quality evidence to distinguish quiet input from provider failure. | Added per-capture UI metrics and cleanup on metric failure; added quiet/active/clipped/empty audio metric tests. |
| Language routing | Earlier report documents default-language misrouting; current adapter explicitly maps English, Telugu, and mixed modes. | Existing mapping retained. All three Prisma client configurations construct successfully. Live transcript quality for each language is still unverified. |

## Command-by-command live acceptance

| Command | Transcript | Gemini Plan | Windows Execution | Verified Result | Status |
|---|---|---|---|---|---|
| “Open Notepad” | No fresh speech | No fresh voice plan | None | Historical direct Notepad launch is recorded in `TEST-EVIDENCE.md`; no fresh voice action | NOT RUN via live voice |
| “Open ChatGPT” | No fresh speech | No fresh voice plan | None | Historical direct browser open is recorded; no fresh voice action | NOT RUN via live voice |
| “Move the cursor” | No fresh speech | None | None | Historical direct cursor movement was verified on the disposable QA page; no fresh voice action | NOT RUN via live voice |
| “Click the first link” | No fresh speech | None | None | Historical harmless click is recorded; no fresh target snapshot or voice execution | NOT RUN via live voice |
| “Scroll down” | No fresh speech | None | None | Historical scroll on the local QA page is recorded; no fresh voice action | NOT RUN via live voice |
| “Type text” | No fresh speech | None | None | Historical scratch-document typing is recorded; no fresh voice action | NOT RUN via live voice |
| “Switch windows” | No fresh speech | None | None | Historical switch between controlled Edge QA and Notepad is recorded; no fresh voice action | NOT RUN via live voice |
| “Open YouTube and search Python tutorials” | No fresh speech | None | None | No live voice run | NOT RUN |
| “Close a disposable test window” | No fresh speech | None | None | Historical disposable-tab close passed; closing a complete window remains unverified | NOT RUN |
| “Emergency Stop” | No fresh speech | None | None | Historical direct companion Emergency Stop passed; no fresh active-sequence stop run | NOT RUN |
| “Open Notepad and type BHASHALEARN AI” (planner probe only) | Typed synthetic text supplied directly to planner, not microphone | Live Gemini initially returned an invalid unbound `type_into`; after repair, returned validated `open_app` + `type` plan | Not executed | Plan validated; no Windows state change claimed | PLANNER VERIFIED; voice/action NOT RUN |

## Runtime/configuration checks

- Gnani Prisma client construction succeeded for default, English, Telugu, and mixed modes. This is configuration readiness, not a live API response.
- `sounddevice` is installed; Windows reports seven input-capable devices and a default input. Device presence does not prove capture quality or permission in the browser.
- Gemini configuration is present using the repository's provider environment loader. One live Gemini request was made with only the synthetic command above; the repaired plan was returned and validated.
- Documented local frontend/API/companion health ports were not listening at audit time. No microphone or Windows UI permission was newly granted, and no physical audio was recorded or transmitted during this run.
- No audio recording, credential value, database, cache, or environment file is included in the source changes.

## Test results

| Check | Result | Scope |
|---|---|---|
| Focused Feature 1 backend suite | 66 passed, 0 failed | Voice endpoint, Gemini plan validation, companion auth, desktop command policy, Windows executor contracts; isolated tests/mocks, no live Windows action |
| Full backend suite | 328 passed, 0 failed, 3 skipped | Full backend suite, including Feature 2 coverage; skips are PostgreSQL-gated |
| Frontend suite | 91 passed, 0 failed | Includes three new microphone-metric tests; deterministic/unit coverage, no physical microphone |
| Production build | Passed | TypeScript and Vite build; existing Three.js chunk exceeds 500 kB advisory |
| Live Gemini plan | Passed after repair | Real provider request and schema validation; action not executed |
| Live Prisma speech | Not run in this pass | No user speech sample was available; prior recorded results were wrong/empty |
| Direct desktop actions | Historical only | See `docs/TEST-EVIDENCE.md` for 2026-11-12 results; not repeated in this run |
| Complete live voice-to-desktop | Not run | No new microphone capture/transcript; no plan reached companion execution |
| `git diff --check` | Passed | final whitespace check |
| Credential/artifact review | Passed | Credential-pattern scan clean; staged allowlist is source, tests, and reports only; build output is ignored |

## Feature 2 regression

Feature 2 code was not modified. Its backend regression coverage is part of the final full backend suite; final count will be recorded after that run completes. The companion allowlist fix is restricted to an existing loopback-only API port boundary.

## Changed files

- `backend/app/services/desktop_commands.py` — guarded normalization for the explicit Notepad open-then-type sequence.
- `backend/tests/test_desktop_commands.py` — planner repair regression coverage.
- `backend/tests/test_desktop_companion.py` and `scripts/desktop_companion.py` — documented loopback backend port allowlist repair and test.
- `frontend/src/VoiceTutor.tsx`, `frontend/src/voiceAudioMetrics.ts`, and `frontend/tests/voice-audio-metrics.test.mjs` — capture-quality diagnostics, UI feedback, cleanup safety and metric tests.
- `docs/FEATURE1-ROOT-CAUSE-REPORT.md` — evidence-separated root-cause analysis with follow-up findings.
- This final report.

No dependency was installed.

## Remaining acceptance items

1. Run the isolated application and companion, grant microphone permission if prompted, speak representative English/Telugu/mixed commands, and capture the new UI audio metrics plus actual Prisma transcripts.
2. Verify the real Gemini plan, companion result, and independently observed Windows state change for each accepted command.
3. Exercise Emergency Stop during a running multi-step command; test window close only against a verified disposable window.
4. Repeat complete backend/frontend/build/security checks after any further acceptance-driven code changes.

Until those checks pass, Feature 1 is not complete. The current code and automated tests are ready for local acceptance, but the recorded low microphone level and lack of a fresh speech sample prevent a claim of end-to-end success.

## Live acceptance run — 2026-11-13

**Status: LOCAL ACCEPTANCE REQUIRED — end-to-end speech-to-desktop acceptance did not pass.** The requested spoken command was attempted in an isolated local session. Gnani Prisma returned incorrect transcripts on both user-approved captures. The mixed-language retry was not performed because the user explicitly stopped voice testing. No Notepad action was executed and no Windows action is claimed.

### Startup, login, and companion

- Continued with the already running local stack; did not restart or rebuild working services. Final read-only checks returned HTTP 200 from backend `/ready` (port 18027) and frontend `/login` (port 15199). The companion service on port 18765 returned its expected unauthenticated response when queried without its session credentials.
- Used a separate Chrome test profile and verified the local origin and BHASHALEARN AI page identity before signing in. The disposable test account was read locally; its password is not reproduced here.
- The Voice Tutor session connected to the existing Windows companion, and Desktop Control was enabled for the isolated test session. Emergency Stop was issued after the attempts; companion control was left disabled. No unrelated tabs or user documents were used.
- Windows microphone consent was enabled. Windows listed seven input-capable devices; the default input was `Microphone (Realtek(R) Audio)` (2 channels, 44.1 kHz). Chrome’s normal microphone permission prompt was approved by the user for the authorized captures.

### Microphone and Prisma evidence

| Capture | User approval and mode | UI metrics | Prisma result | Subsequent stages |
|---|---|---|---|---|
| Initial unintended ambient capture | **Not approved.** An earlier Playwright profile unexpectedly entered recording after its permission state changed from `prompt`. This process error was disclosed to the user. | 5.5 s; RMS −36.5 dBFS; peak −12.0 dBFS; speech-level frames 30.6%; clipped 0%. No audio file was retained locally. | HTTP 200; empty transcript. | No Gemini plan or desktop action. |
| Spoken Notepad command | Approved; English | 6.1 s; RMS −20.6 dBFS; peak −0.5 dBFS; speech-level frames 65.0%; clipped 0%. | Incorrect: “Open Notepad and type ‘Bash Learn AI’.” | Gemini displayed an open-Notepad-then-type plan. It was canceled because the dictated product name was wrong. No companion execution or Notepad action. |
| Spoken retry | Approved; English | 8.4 s; RMS −21.3 dBFS; peak approximately 0 dBFS; speech-level frames 74.5%; clipped 0%. | Incorrect: “Open Notepad and and reply, Barsha, learn AI.” | Auto-interpret was disabled; no Gemini request or desktop action. |
| Mixed-language retry | Not performed | — | — | User said “Stop voice testing here”; testing stopped as requested. |

The two approved captures had healthy signal level and substantial speech activity, and the intended Realtek input was already selected as the Windows default. The observed blocker is Prisma recognition of the spoken product name in this run, rather than a quiet microphone or missing Windows input permission. The first unauthorized capture was a procedural error; it was disclosed, was not retained as a local audio file, and was not repeated. Provider-side retention cannot be verified from this session.

### Command acceptance results

| Requested command/action | Result |
|---|---|
| “Open Notepad and type BHASHALEARN AI” | **Failed at transcript validation.** No Notepad was opened and no text was typed. |
| Open ChatGPT; scroll; move cursor; harmless link click; switch windows; YouTube search; close disposable window; Emergency Stop during an active sequence | Not tested in this live run. Emergency Stop was issued only after the failed voice attempts, not during a multi-step action. |
| Telugu and mixed-language commands | Not tested. The user stopped before an additional mixed-language capture. |

No microphone sample was sent to Gemini after the inaccurate retry transcript. The earlier spoken attempt produced a visible Gemini plan, but it was not approved for execution due to transcript mismatch. No companion action response or resulting Notepad state exists for this run.

### Regression status and Feature 2

No source code was changed during this live continuation. The latest available regression results from the preceding pushed source state are: backend 328 passed, 3 skipped; frontend 91 passed; production build passed with the existing large Three.js chunk advisory. These were not rerun because this continuation only adds this report evidence. Feature 2 source was not changed; its existing backend coverage was included in that reported backend suite.

### Final disposition

Feature 1 remains **incomplete**. The minimum next acceptance step is a separately authorized Prisma tuning/diagnostic session, followed by a fresh user-approved spoken command only if the user chooses to resume. This report does not claim successful microphone-to-Windows execution, completion of representative commands, or a completed live acceptance.
