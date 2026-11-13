# Feature 1 — Local Voice Acceptance Checklist

**Status:** Not accepted until a real spoken command changes a disposable Windows window and independent observation confirms it.

## Safety before any run
- Rotate the exposed disposable test-account password; never paste passwords or provider keys into chat or logs.
- Never start a microphone recording without a fresh, explicit user approval. Browser permission alone is not approval.
- Each approval is for exactly one recording. The user starts and stops it visibly.
- Do not upload audio to Prisma until the user has listened to the local preview and clicks **Send reviewed recording to Prisma**.
- Do not send an incorrect transcript to Gemini; do not execute a desktop action without reviewing and confirming its plan.
- Keep desktop control disabled until the approved execution step; use disposable Notepad/browser windows only.

## Diagnostic sequence
1. Open the isolated Voice Tutor session and select **English**.
2. Click **Refresh devices** and select the intended microphone, or use System default.
3. With fresh permission, click **Start microphone recording**; speak `Open Notepad`; click **Stop recording** immediately.
4. Play the **local recording preview**. If it contains unrelated speech, silence, distortion, or the wrong input, **Discard** and investigate the device/browser path without contacting Prisma.
5. If the preview audibly contains the intended phrase, explicitly approve **Send reviewed recording to Prisma**. Record duration, sample rate, RMS, peak, speech-active percentage, provider model, language code, format, latency, and transcript. Do not save raw audio or credentials in reports.
6. If Prisma is wrong, stop before Gemini. With separate explicit approval for each upload, compare the **same approved recording** under `en-IN/transcribe` and `indic-auto/codemix` through a diagnostic-only path; never silently send to a different provider.
7. If transcript is correct, review the structured Gemini proposal. With user confirmation, execute only `open_app(notepad)` through the paired loopback Windows companion.
8. Independently verify a newly opened disposable Notepad is foreground. Stop desktop control immediately afterward.

## Acceptance matrix
- English Notepad open: NOT YET PASSED.
- ChatGPT browser open: NOT YET PASSED via voice.
- YouTube search: NOT YET PASSED via voice.
- Cursor movement/click, scroll, typing, window switching: NOT YET PASSED via voice.
- Disposable-window close with extra confirmation: NOT YET PASSED via voice.
- Emergency Stop during an active multi-step command: NOT YET PASSED.
- Telugu and mixed-language commands: NOT YET PASSED.

## Regression gate
The `.github/workflows/feature1-regression.yml` workflow runs the backend suite, frontend unit tests, frontend production build, and tracked-artifact checks on the feature branch and relevant pull requests. It does **not** access a physical microphone, call live providers, or control Windows. GitHub CI success is not Feature 1 acceptance.

## Known unresolved issues
- A short spoken command was captured for 30 seconds; audio-energy-based silence detection may not have triggered because ambient activity remained above its threshold. The actual captured audio was not retained.
- Prisma returned unrelated Telugu text for an English-mode recording. The cause is not established.
- The current microphone preview lets the user distinguish wrong input from provider transcription errors without automatically uploading audio.
