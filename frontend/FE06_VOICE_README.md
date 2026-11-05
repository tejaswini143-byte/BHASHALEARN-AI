# FE-06 / INT-03 — Gnani Voice Classroom

## Implemented

- Browser microphone recording is linearly resampled to 16 kHz mono PCM WAV, capped at 30 seconds, and microphone tracks are released after capture.
- Authenticated upload to `POST /api/v1/voice/sessions/{session_id}/transcribe` calls the existing POC-01 Gnani Prisma client. The raw transcript is editable before sending.
- The existing `POST /api/v1/tutor/sessions/{session_id}/chat` endpoint remains the only tutoring and chat-persistence path. A completed voice question produces one user/assistant pair.
- Authenticated `POST /api/v1/voice/sessions/{session_id}/speech` calls the existing POC-02 Timbre client through the POC-06 adapter and returns playable WAV.
- English, Telugu, and mixed tutor preferences; saved session context; explicit transcription, tutor, and speech states; text fallback; speech retry/replay; and speech failure recovery.
- TTS retries use the existing assistant text and do not re-submit the student turn to Gemini. TTS failure leaves the saved text conversation intact.

## Provider contracts and limitations

Prisma uses the existing POC-01 configuration, including `indic-auto` and
`codemix` defaults. The UI's language mode is a tutor preference; it does not
claim that Prisma receives a separate English or Telugu model selector. POC-01
validates uncompressed PCM WAV, up to 10 MiB and 30 seconds. Timbre uses its
verified POC-02 English (`en-IN` / Kaveri) and Telugu (`te-IN` / Suhana)
settings. Mixed tutor responses are segmented by script using POC-06 and
per-language WAV frame data is joined. Language boundaries may sound abrupt;
listener quality review remains necessary. No audio recordings are persisted.

The waveform is a recording indicator, not a microphone-amplitude display.
Streaming, speech scoring, lip-synced avatars, and reliable automatic
code-switch recognition are outside this integration. Browser mic permission,
audio playback, and autoplay policy vary by browser. INT-02 Gemini live status
remains as previously reported and is not re-verified by this task.

## Windows CMD verification

From the repository root, install backend dependencies and run the focused and
full regression tests:

```cmd
python -m pip install -r backend\requirements.txt
python -m pytest -q backend\tests\test_voice.py
python -m pytest -q backend\tests
```

Start backend and frontend in separate CMD windows:

```cmd
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8002
```

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-AI\frontend
set BHASHALEARN_API_PROXY_TARGET=http://127.0.0.1:8002
npm.cmd run dev -- --host 127.0.0.1
npm.cmd run build
```

Open the printed Vite URL, sign in, visit `/voice`, choose a tutor language,
record and stop, inspect/correct the transcript, and send it. Confirm that the
assistant reply appears in saved history, then use **Listen / replay**. Deny
microphone permission and verify typed chat remains available. Repeat in
English and Telugu; try a mixed-language clip and review recognition and audio
quality separately. Reload the selected session and confirm the same
chronological history. Mocked tests do not establish live provider or browser
acceptance.

## Configuration and security

The backend uses `GNANI_API_KEY` and the existing `GNANI_STT_*`, `GNANI_MODEL`,
`GNANI_LANGUAGE`, `GNANI_OUTPUT_FORMAT`, and `GNANI_TTS_*` variables. Local
provider settings may remain in their POC `.env` files. Credentials stay on the
server; never use frontend environment variables for provider keys or commit
`.env` files. Request errors do not include secrets, uploaded audio, or provider
response bodies.
