# Feature 1 Root Cause Report

Audit date: 2026-11-13 (Asia/Kolkata)
Repository: `C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109`
Branch: `integration/release-candidate-20261109`
Audited HEAD: `4fe57412596b3619941897246c1109686bd91e5b`

## 1. Current architecture

1. The authenticated Voice Tutor requests microphone permission only after the user presses its microphone control. It captures one-channel audio through `getUserMedia`, creates an AudioContext, detects speech onset with an RMS threshold, stops capture on user action or timeout, and converts captured Float32 chunks into PCM WAV.
2. The browser submits WAV plus selected `english`, `telugu`, or `mixed` mode to `/api/v1/voice/sessions/{session_id}/transcribe` with the student's bearer token.
3. The FastAPI endpoint checks session ownership, request limits, WAV filename/type/size and audio structure, creates a language-specific Prisma adapter, calls Gnani, and returns a transcript. The user can review/correct the transcript before using it.
4. Desktop Control receives the transcript only when opt-in voice commands are enabled. A stop phrase is handled locally. Other commands are sent to the authenticated backend, where Gemini returns an action conforming to a strict Pydantic schema and policy validation.
5. The browser pairs with the user-started desktop companion over loopback using a pairing token. The UI displays the plan and requires confirmation; closing a window has a separate confirmation. The companion revalidates targets/actions and uses the Windows automation module to perform the action. Emergency Stop disables control and cancels remaining sequence steps.
6. The companion reports execution outcomes to the UI. Actual desktop state must be independently observed to establish success.

## 2. Findings by stage

### VERIFIED WORKING

- Repository HEAD equals the supplied last verified SHA, and the branch is the requested integration branch. Git status was clean at audit start.
- Voice API source supports authenticated, session-owned uploads, 10 MB maximum size, WAV validation, language-specific Prisma client selection, safe provider errors, and rate limiting.
- Current frontend source requests mono capture with echo cancellation, noise suppression, and auto gain control; captures via AudioContext; serializes WAV; and sends the selected language mode.
- Current voice UI explicitly asks for microphone access on user action and lets the user review/edit the transcript before sending it onward.
- Gemini desktop planning is constrained by a typed action schema and policy validation. Plans require UI confirmation; arbitrary shell commands are not an action type.
- Desktop companion source and runbook describe loopback-only binding, pairing/authentication, opt-in activation, allowlisted operations, separate close confirmation, and Emergency Stop.
- Prior direct Windows evidence in `docs/TEST-EVIDENCE.md` records successful cursor movement/click, scroll, open ChatGPT, Notepad typing in a scratch document, window switching, disposable-tab close, and Emergency Stop. These are historical direct-desktop checks, not current-run verification.
- Prior regression evidence records passing backend and frontend tests/build on 2026-11-12, including Feature 2 in the full backend suite. This audit has not rerun them yet.

### CONFIRMED FAILURE

- **Prisma transcript did not yield a usable command in the latest recorded live capture.** `docs/TEST-EVIDENCE.md` reports two seven-second captures sent through the authenticated isolated backend. Both returned HTTP 200, but the first transcript did not match the requested command and the retry contained zero characters. Thus no transcript reached Gemini and no voice-planned companion execution occurred. HTTP success is not acceptance.
- **Microphone input level was insufficient for reliable recognition in the latest measured sample.** The evidence records RMS −45.9 dBFS, peak 1,029/32,767, and only 28.4% of 20 ms frames above −45 dBFS. Prisma returned an empty transcript for the English route. This confirms poor capture level and failed recognition for that sample, not a universal hardware defect.

### SUSPECTED ISSUE

- The current RMS onset threshold may still discard quiet speech or include excessive leading noise; the available report gives measured input metrics but does not preserve samples or include a new live capture after the latest threshold/auto-gain changes.
- The browser's reported microphone permission/device state may differ by browser profile or OS privacy configuration. No current permission UI/device inventory was collected in this audit.
- Empty or wrong transcripts may also depend on physical microphone selection, room noise, provider model behavior, network conditions, or speech-language mismatch. Existing evidence is insufficient to isolate which of these contributed beyond the low measured level.
- Emergency Stop interrupts in-progress sequences according to source and prior safe action evidence, but there is no captured race-condition test proving cancellation during a live Windows action.

### NOT TESTED IN THIS AUDIT

- Fresh microphone capture, permission/device state, live audio metrics, and new Prisma calls.
- Live Gemini desktop planning from a fresh transcript; structured result behavior against a real provider for each representative command.
- Complete current voice-to-Gemini-to-companion-to-observed-Windows-state flow.
- Live English, Telugu, and code-mixed desktop command recognition.
- Current Windows app/browser navigation, target identification on arbitrary pages, multi-step workflow, and complete-window close safety.
- Emergency Stop during an actively executing multi-step workflow.
- Current full backend/frontend suites, production build, Feature 1 integration suite, Feature 2 regression suite, and credential scan.
- Provider configuration validity at runtime. No credential values were read or exposed.

## 3. Root causes and impact

| ID | Classification | Root cause/evidence | Severity and impact | Repair/checklist |
|---|---|---|---|---|
| R1 | Confirmed | Captured signal was very quiet (RMS −45.9 dBFS; peak 1,029/32,767; 28.4% frames above −45 dBFS), followed by an empty Prisma result. | Blocker for spoken commands on the measured setup; later stages receive no command. | Recheck device selection, permission and capture signal; expose useful quality/status feedback; tune capture only against live evidence. |
| R2 | Confirmed | A separate live capture returned a transcript that did not match the requested command; the retry returned empty. | Critical safety/quality risk: wrong intent must never execute; user review is present, but voice command reliability is unproven. | Preserve transcript review and no-action-on-empty behavior; repeat controlled spoken samples and record each stage/result. |
| R3 | Prior issue, reported fixed | Earlier session route created Prisma from environment defaults despite selected language. `create_prisma_client_for_language` now maps English to `en-IN/transcribe`, Telugu to `te-IN/transcribe`, mixed to `indic-auto/codemix`. | Could degrade language recognition; latest routing change has offline coverage but does not establish live quality. | Keep mapping, test each mode, confirm actual provider request configuration without exposing secrets. |
| R4 | Unverified integration | No accepted transcript means Gemini, companion, and Windows execution did not run for the voice path. | End-to-end feature remains incomplete even though component/direct tests exist. | Conduct controlled end-to-end acceptance after transcript quality succeeds. |

No missing Python desktop package is indicated by the existing runbook: it requires `numpy`, `sounddevice`, `pyautogui`, `pygetwindow`, and `pywinauto` in the project or approved safe virtual environment. Their present install/runtime status was not rechecked. Browser and Windows microphone permission state is likewise unverified.

## 4. Reproduction from existing evidence

The historical failure record is in `docs/TEST-EVIDENCE.md` under “Windows desktop integration — 2026-11-12” and “Voice transcription follow-up — 2026-11-12”:

1. Start the isolated backend and frontend as documented in `docs/LOCAL-DEMO-SETUP.md`; sign into a synthetic student session.
2. Open Voice Tutor, choose a language mode, explicitly start a microphone capture, speak the test command, then stop capture.
3. Inspect the actual transcript and capture metrics; do not treat HTTP 200 as a pass.
4. Historical result: two seven-second captures; one wrong transcript, one empty transcript; measured quiet input in the later sample; Gemini and companion were not called.

This audit did not repeat the live reproduction, so the result above is historical evidence rather than a fresh run.

## 5. Existing architecture/security boundaries and gaps

- Existing security controls include authenticated backend routes, session ownership, loopback-only companion, pairing token, explicit opt-in enablement, action allowlists, typed plan validation, human confirmation, extra confirmation for closing windows, and Emergency Stop.
- No evidence supports weakening these controls. A complete-window close was previously not run because the disposable state could not be established safely.
- Existing capability source includes mouse movement/click, scrolling, typing, shortcuts, browser/site actions, app/window controls, search, visible target identification, and bounded sequences. Some targets/actions are only source-level or unit-tested; the requested representative live end-to-end capability set is not proven.
- No audio recordings are retained in the evidence; only metrics/transcript length were recorded. No credentials were printed or copied in this audit.

## 6. Acceptance tests required

1. **Capture and permissions:** Verify browser permission granted, selected input device, mono PCM WAV properties, duration, clipping, RMS/peak and speech-active frame share for English, Telugu, and mixed speech. Test empty input, denied permission, device unavailable, and quiet speech; errors must be clear and no empty transcript may proceed.
2. **Prisma live:** For each language mode, capture a controlled command and compare transcript to the expected phrase. Record status, language request configuration, detected language, transcript, latency and safe provider error. Keep audio ephemeral.
3. **Gemini live planning:** Submit a confirmed transcript and record the validated structured plan. Test ambiguous request -> clarification, unsupported request -> refusal, malformed plan -> reject, and all action types with schema/policy validation. Never execute a raw model string.
4. **Companion auth/routing:** Verify pairing with the intended local companion, reject missing/invalid token and remote host, enforce explicit Enable Control, and reject stale/changed UI target snapshots.
5. **Direct Windows effects:** Use controlled Notepad scratch content and disposable browser pages/windows. Independently verify cursor position, harmless click, scroll position, typed text, shortcut, website open/search, window switch/minimize/maximize, and close only a known disposable test window.
6. **Sequences and stop:** Execute a bounded multi-step workflow with per-step verified state. Trigger Emergency Stop during a sequence and prove remaining steps do not execute and control remains disabled until re-enabled.
7. **Full voice path:** For each spoken test, retain a redacted evidence row with microphone status/metrics, Prisma transcript, Gemini plan, companion result, independently observed Windows state, and final pass/fail. Include Notepad, ChatGPT, move/click, scroll, type, switch, YouTube search, disposable-window close, and Emergency Stop.
8. **Regression/security:** Full backend and frontend suites, frontend production build, Feature 1 integration tests, Feature 2 regression tests, `git diff --check`, and credential/artifact scan. Do not include recordings, databases, ignored environment files, or caches.

## 7. Evidence limits

This report combines source inspection and prior recorded evidence. The report does not claim a new physical microphone test, live provider response, Gemini action plan, or end-to-end Windows state change. The exact blocking dependency for completing live acceptance must be determined by a fresh controlled run; current records point to very low microphone input and unreliable Prisma output as the first blocker.

## 8. Follow-up findings and repairs — 2026-11-13

- **CONFIRMED FAILURE — Gemini emitted an unbound Notepad typing step.** A live Gemini request for the harmless command “Open Notepad and type BHASHALEARN AI” returned a sequence with `open_app(notepad)` followed by `type_into` without a `target_id`. Strict schema validation correctly rejected this with HTTP 502; no action was executed. The action is inherently dynamic because the Notepad document does not exist in the pre-execution snapshot.
- **Repair:** For the one explicit sequence case containing `open_app(notepad)` followed by `type_into` with no target and the local `[LOCAL_DICTATION]` sentinel, normalize that step to the existing guarded `type` action. The Windows executor then confirms Notepad is foreground and uniquely identifies its editable document before typing. Other unbound `type_into` plans remain invalid. A regression test covers both accepted and rejected shapes.
- **VERIFIED WORKING after repair — live Gemini plan:** Repeating the same provider request returned the schema-validated `open_app(notepad)` then `type("BHASHALEARN AI")` sequence. It was not executed.
- **CONFIRMED FAILURE — documented companion API port omitted from local allowlist.** The companion's `ALLOWED_API_PORTS` omitted 18027 although `docs/LOCAL-DEMO-SETUP.md` uses `127.0.0.1:18027`; `/background/enable` rejected the documented URL before session verification.
- **Repair:** Added only 18027 to the existing loopback API port allowlist. A test accepts that documented localhost URL and rejects an unlisted localhost port. The existing local-origin and bearer-session checks remain enforced.
- **CONFIRMED OBSERVABILITY GAP — capture quality was not retained or shown.** Runtime code used per-buffer RMS only for VAD and discarded duration, overall RMS, peak/clipping, and active-frame percentage, making it impossible to distinguish a quiet capture from a provider failure in the UI.
- **Repair:** The Voice Tutor now displays last-capture duration, RMS dBFS, peak dBFS, speech-level frame percentage, clipping percentage, and a low-input hint; it also shows the outgoing WAV byte size. A cleanup safeguard releases the microphone even if metrics collection fails. Unit tests cover quiet, active/clipped, and empty captures.
- **Current setup check:** Gnani Prisma can be constructed for default, English, Telugu, and mixed modes without exposing credentials. `sounddevice` is installed; Windows reports seven input-capable devices and a default input. This checks configuration/device presence only; no audio was captured in this audit.
- **Current runtime check:** No documented local frontend, API, or companion health endpoint was listening during this audit. No user speech sample was available. The historical Prisma results therefore remain the latest actual STT evidence: one incorrect and one empty transcript.
- **Revised disposition:** Provider configuration and device availability are present, but real Prisma transcript quality and full voice-to-Windows acceptance remain NOT TESTED in this run. Prior direct Windows action evidence remains historical and must not be conflated with voice-driven execution.

## Recovery investigation — 2026-11-13

**Root cause status: unresolved.** The live attempts establish that Prisma returned inaccurate text for two approved English captures, but their WAV files were not retained. There is no authorized spoken WAV fixture in the repository, so the waveform from those failed requests cannot now be inspected or replayed safely. No provider call was made with synthetic tones.

### POC-01 comparison

The current production adapter delegates to POC-01's PrismaSTTAdapter. The endpoint default, X-API-Key-ID header, audio_file multipart field, audio/wav MIME type, prisma-v3.0 model, timeout/error handling, and supported response extraction match the POC contract. Both paths validate uncompressed PCM WAV before upload. The successful HTTP responses also show that the live request reached a provider endpoint and produced a parseable response; they do not establish that the audio encoding or language selection was optimal.

One concrete request difference remains: the production English mode sends language_code=en-IN, format=transcribe; Telugu sends te-IN/transcribe; mixed sends indic-auto/codemix. POC-01's verified default is indic-auto/codemix. The two latest approved live attempts used English mode. This is a plausible recognition-quality variable, but no controlled recording exists to establish it as the cause. It is intentionally left unchanged pending a permitted one-variable live comparison.

### Browser audio path

The browser captures mono Float32 audio at the active AudioContext rate, applies browser echo cancellation, noise suppression and automatic gain control, then resamples to mono 16 kHz PCM16 WAV. The prior resampler averaged output bins, which provided only a weak anti-alias filter before decimation. It has been replaced with a windowed-sinc low-pass resampler. This is a confirmed encoding-quality improvement, but without the original live waveform it cannot be declared the cause of the Prisma transcript errors.

A new deterministic synthetic transport test confirms RIFF/WAVE PCM, one channel, 16 kHz, 16-bit samples, expected duration and preservation of a 1 kHz signal. A 12 kHz synthetic input is attenuated below 0.005 RMS after 3:1 downsampling. These synthetic tones validate encoding and filtering only; they say nothing about speech recognition accuracy.

### Additional safety and observability repairs

- The desktop panel no longer sends each new Prisma transcript to Gemini automatically. The user must explicitly mark the transcript reviewed before asking Gemini for a plan, and the resulting plan still requires separate execution confirmation.
- A synthetic open_app(notepad) plan was initially blocked because the accessibility tree changed after planning. App launch does not depend on a UI target; the panel now uses a fresh companion snapshot for target-independent actions and retains strict equality checks for target-bound actions.
- The transcription response now reports Prisma provider/model/status/latency, the actual language code and format sent, and the sample rate/channel/bit depth read from the uploaded WAV header. The Voice Tutor displays these alongside capture duration, source rate, RMS, peak, speech-active percentage and clipping.
- No fallback STT provider was added and no audio was sent to another provider.

### Evidence boundaries

The 2026-11-13 live report records the precise historical capture metrics and Prisma transcripts. Both approved English transcripts were wrong; the second was not forwarded to Gemini. One earlier capture was unapproved ambient audio and returned an empty transcript; that process error is disclosed in the final test report. No audio file was retained locally, and provider-side retention cannot be verified.

Offline POC-01 adapter tests passed 8/8; the backend suite passed 328 with 3 skipped; frontend tests passed 96/96; and the production build passed with the existing Three.js chunk-size advisory. Feature 2 source was not changed, and its backend tests remain included in the full backend suite.

Phase C checks used synthetic text and one explicitly confirmed disposable Notepad action. The real Gemini planner returned open_app(notepad); the authenticated companion executed that diagnostic plan; independent Windows checks found Notepad foreground and one editable text target. Emergency Stop then left companion control disabled. This is not voice acceptance.

No new microphone recording has been made in this recovery attempt. The browser permission state was granted, but that state was not treated as permission to record. The requested real spoken test remains pending fresh explicit user approval.
