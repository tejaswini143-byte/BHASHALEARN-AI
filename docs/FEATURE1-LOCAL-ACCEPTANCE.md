# Feature 1 — Local Voice Acceptance Checklist

**Status:** Not accepted until a real spoken command changes a disposable Windows window and independent observation confirms it.

## Safety before any run
- Rotate the exposed disposable test-account password; never paste passwords or provider keys into chat or logs.
- Never start a microphone recording without a fresh, explicit user approval. Browser permission alone is not approval.
- Each approval is for exactly one recording. The user starts and stops it visibly.
- Do not upload audio to Prisma until the user has listened to the local preview and clicks **Send reviewed recording to Prisma**.
- Do not send an incorrect transcript to Gemini; do not execute a desktop action without reviewing and confirming its plan.
- Keep desktop control disabled until the approved execution step; use disposable Notepad/browser windows only.

## Start a disposable Windows test stack

Use a disposable Windows desktop session with a microphone and a fresh checkout of PR #2. From the repository root in PowerShell, with Python 3.13 and Node.js 22 available:

```powershell
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r scripts\requirements-desktop.txt
Copy-Item backend\.env.example .env
```

Edit the ignored root `.env` locally. Set `BHASHALEARN_DATABASE_URL=sqlite:///./feature1-acceptance.sqlite3`, generate a fresh `BHASHALEARN_JWT_SECRET_KEY`, and configure valid `GNANI_API_KEY` and `BHASHALEARN_GEMINI_API_KEY` values. Set `BHASHALEARN_GEMINI_MODEL` to the model available to the test account. Use a new SQLite filename for each clean acceptance setup.

In the first PowerShell window:

```powershell
& .\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
& .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8027
```

In a second PowerShell window from the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

In a third PowerShell window from the repository root:

```powershell
& .\.venv\Scripts\python.exe scripts\desktop_companion.py
```

Open `http://127.0.0.1:5173/register` in a fresh browser profile, create a disposable student, then open `http://127.0.0.1:5173/voice`. Create a session with **New learning topic → + Create**. Leave desktop control disabled until the spoken command has been captured, reviewed locally, and correctly transcribed. For the Phase 1 check, the exact English “Open Notepad” command is planned in the browser and requires no Gemini key. Gnani credentials are still needed for live Prisma transcription. Optional Timbre feedback uses the configured Gnani account.

## Diagnostic sequence
1. Open the isolated Voice Tutor session and select **English**.
2. Click **Refresh devices** and select the intended microphone, or use System default.
3. With fresh permission, click **Start microphone recording**, accept the app consent dialog, and allow browser microphone access if prompted. When the recorder shows **Recording**, speak `Open Notepad`; click **Stop recording** immediately.
4. Play the **local recording preview**. If it contains unrelated speech, silence, distortion, or the wrong input, **Discard** and investigate the device/browser path without contacting Prisma.
5. If the preview audibly contains the intended phrase, explicitly approve **Send reviewed recording to Prisma**. Record duration, sample rate, RMS, peak, speech-active percentage, provider model, language code, format, latency, and transcript. Do not save raw audio or credentials in reports.
6. If Prisma is wrong, stop before preparing an action. With separate explicit approval for each upload, compare the **same approved recording** under `en-IN/transcribe` and `indic-auto/codemix` through a diagnostic-only path; never silently send to a different provider.
7. If the transcript is correct, click **Connect to local companion → Enable control → I reviewed this transcript → Prepare Notepad action**. Verify the plan proposes only opening Notepad. With separate authorization for that action, click **Confirm and execute** and approve the matching native Windows prompt.
8. If Notepad reports that no new window was verified, check whether its scratch document opened in an existing tab. In the disposable profile, close existing Notepad windows or select the Notepad setting to open files in a new window before requesting fresh approval for a retry. Independently verify a newly opened disposable Notepad is foreground. Click **Emergency Stop** immediately afterward. Check that the panel offers **Enable control** and the plan button is disabled. Report the commit, preview match, Prisma diagnostics and transcript, proposed action, whether both confirmations appeared, independent observation of Notepad, and the Stop result. Share no raw audio, credentials, or unredacted network exports.

## Phase 2 approved links

Use a disposable browser profile. Record “Open YouTube” and listen to the local
preview. With separate approval, send it to Prisma. Review the returned text,
then choose **I reviewed this transcript → Prepare link action**. Verify the
browser proposal and native Windows prompt both show
`https://www.youtube.com/`. With separate approval, confirm and check that the
intended page appears in the default browser. The app reports dispatch to the
browser. Page loading is verified by the operator.

The same path supports “Open ChatGPT” and “Open Google.” The planner also
accepts the common transcript spellings “You Tube” and “Chat GPT.”
If the companion loses its response after confirmation, check the browser
before preparing a fresh action. If Windows reports a dispatch failure, check
the default browser configuration. To test clarification,
try the reviewed text “Open the website Example.” The panel should list the
approved links and offer no execution button. These exact link commands are
planned locally. No Gemini key is needed.

## Phase 3 cursor and named buttons

In a disposable Chrome or Edge window, open the local
`/desktop-control-test.html` page and use its embedded Voice Tutor. Keep
the QA window in the foreground and place the cursor away from its edges. Use a fresh
approved recording and Prisma upload for each live command.

- Say “Move the cursor right.” Review the transcript and select **Prepare
  pointer action**. Approve both prompts and observe the bounded movement.
- Say “Click Test button.” Verify the exact label in the proposal and native
  prompt. After both approvals, check that the button changes to **CLICK VERIFIED**.
- Say “Click Open chapter.” The two matching buttons should produce a
  clarification without an execution button. Change the window or button after
  planning to check that stale targets are rejected. Try switching tabs or disabling the button before a click. If a companion response is lost, inspect the page before preparing a fresh action.

The companion reports that it sent the click. Verify the visible page change
separately and use **Emergency Stop** when finished.

## Phase 4 dictated text

Use the embedded Voice Tutor on the disposable `/desktop-control-test.html`
page, with the QA browser window in the foreground. Record “Type Hello from
BHASHALEARN” and review the local clip before approving Prisma upload.
Review the transcript and select **Prepare text entry**. Verify the proposal
and native prompt show the exact text and **Permitted text field**. After
both approvals, check that this field contains the reviewed text.

This action replaces the value in the named demo field through Windows UI
Automation. It does not send global keystrokes or submit a form. Switch tabs
or disable the field after planning to verify that the operation is blocked.
Try saying just “Type” to verify that the panel asks for text without offering
execution. Moving keyboard focus within the same QA window is expected when
clicking approval controls. The write remains bound to the original named field.
If Windows cannot verify the field value, inspect it before approving a retry.

## Phase 5 demo autofill

Open the disposable `/desktop-control-test.html` page on an approved QA
port and use its embedded Voice Tutor. Record “Fill the demo form,” listen
to the preview, and approve Prisma submission. After reviewing the transcript,
select **Prepare demo autofill**. Confirm that both the browser preview and
Windows prompt show **Name → Demo Learner** and **Email →
demo.learner@example.test**.

With separate approval, execute the plan and verify both field values. The
form should remain unsubmitted until you click **Submit demo form**. The demo
submit button confirms locally. Switch tabs or disable one field before
execution to check that the action is rejected. If Windows reports an
unverified write or you stop between writes, inspect both fields before a retry.
With fresh approval, a retry skips any field that already has its approved value.

## Acceptance matrix
- English Notepad open: NOT YET PASSED.
- ChatGPT browser open: NOT YET PASSED via voice.
- YouTube search: NOT YET PASSED via voice.
- Cursor movement/click, scroll, typing, window switching: NOT YET PASSED via voice.
- Disposable-window close with extra confirmation: NOT YET PASSED via voice.
- Emergency Stop during an active multi-step command: NOT YET PASSED.
- Telugu and mixed-language commands: NOT YET PASSED.

## Regression gate
The `.github/workflows/feature1-regression.yml` workflow runs the backend suite, frontend unit tests, a headless browser voice flow with synthetic audio and mocked providers, the frontend production build, and tracked-artifact checks on the feature branch and relevant pull requests. It does **not** access a physical microphone, call live providers, or control Windows. GitHub CI success is not Feature 1 acceptance.

## Prior incident evidence

- The earlier `Completed: completed open_app` banner could reflect a late response from an earlier request. No matching browser request trace or companion execution record was available to establish whether Windows actually opened an app. The browser rejects stale completions, and the companion now invalidates pending approval and execution when control is stopped, disabled, or re-enabled.
- The [earlier test report](FEATURE1-FINAL-TEST-REPORT.md#microphone-and-prisma-evidence) records a 5.5-second unauthorized ambient capture after the browser permission state changed from `prompt`, followed by Prisma HTTP 200 with an empty transcript. Whether the separately reported five-second preview refers to that same capture is unconfirmed. No corresponding event trace establishes what started recording, and provider retention is unknown. The current Voice Tutor opens the microphone only through the recording button and a separate consent dialog. Dismissing consent preserves the previous preview, and upload requires its own button.

## Known unresolved issues
- A short spoken command was captured for 30 seconds; audio-energy-based silence detection may not have triggered because ambient activity remained above its threshold. The actual captured audio was not retained.
- Prisma returned unrelated Telugu text for an English-mode recording. The cause is not established.
- The current microphone preview lets the user distinguish wrong input from provider transcription errors without automatically uploading audio.
