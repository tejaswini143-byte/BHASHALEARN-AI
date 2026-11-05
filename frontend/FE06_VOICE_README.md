# FE-06 — Browser Voice Tutor

## Implemented
- Protected `/voice` route linked from dashboard and text classroom.
- Microphone recognition using browser Web Speech API (SpeechRecognition/webkitSpeechRecognition) where available, with editable transcript before sending.
- Animated microphone orb and waveform, recording state, microphone permission and recognition error feedback.
- English (India) and Telugu (India) recognition language options; mixed mode uses English (India), not true simultaneous bilingual ASR.
- AI tutor requests through existing `POST /api/v1/tutor/sessions/{session_id}/chat` and persisted conversation history through `GET /api/v1/sessions/{session_id}/messages`.
- Browser speech synthesis playback for individual tutor messages and optional auto-read replies.
- Session selection, session creation, mobile layout, and clear empty/error states.

## Not yet integrated
- Gnani Prisma speech recognition and Timbre voice synthesis are **not** connected to FastAPI in this phase. Existing POC code is not automatically a production voice endpoint.
- No real-time streaming, speech scoring, lip-synced avatar, or reliable code-switching recognition.
- Animated waveform is a recording-state indicator, **not measured microphone amplitude**.
- Browser speech recognition availability, privacy and network behavior depend on the browser; recognition may be processed by the browser vendor.
- Tutor requests require a valid configured Gemini API key on the backend; live provider calls remain unverified.

## Windows local test
```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
git fetch origin
git switch feature/fe-06-voice-tutor
git pull origin feature/fe-06-voice-tutor
```
Start backend from repository root: `python -m uvicorn backend.app.main:app --reload` with venv active. Start frontend from `frontend` with `npm run dev`; verify `npm run build`. Open http://localhost:5173/voice, log in if needed, select/create a topic, click the microphone, allow permission, speak, review the transcript, click **Send to tutor**, and use **Listen** on a tutor reply. Try both languages and disable microphone permissions to verify error handling. Use Chrome or Edge for the best chance of browser recognition support.

Never put API keys in frontend files or share secrets in screenshots.
