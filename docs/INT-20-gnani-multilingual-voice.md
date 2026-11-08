# INT-20 Gnani multilingual voice teaching

## Provider boundary

The authenticated backend reuses the checked-in POC clients instead of defining a new provider protocol:

- Prisma STT uses the existing REST adapter at `POST https://api.vachana.ai/stt/v3`, header `X-API-Key-ID`, multipart `audio_file`, and the repository's `prisma-v3.0`, `indic-auto`, `codemix` settings. Requests accept bounded PCM WAV; provider timeouts and malformed replies map to safe HTTP errors.
- Timbre TTS uses the existing REST adapter at `POST https://api.vachana.ai/api/v1/tts/inference`, header `X-API-Key-ID`, and its existing JSON/WAV client. POC-06 segments mixed English/Telugu text using its recorded English and Telugu voice pairs. No audio timing or visemes are fabricated.
- Credentials are loaded by the existing environment-based factories. `GET /api/v1/voice/sessions/provider-mode` reports credential readiness without sending provider requests or returning secret values.

These are the contracts implemented by the repository clients. The linked Gnani documentation endpoints were inaccessible during INT-20 review, so this task does not claim fresh official-document verification. No live Gnani call was made. Prisma/Timbre language support and pronunciation quality therefore remain unvalidated with current credentials and reviewed clips.

Prisma is a bounded recorded-audio REST path; it does not provide incremental transcript events in this integration. The UI records up to 30 seconds, shows the completed transcript for review, and supports typed Telugu, Romanized Telugu, English, and code-mixed text. A live partial transcript is not claimed.

## Session language policy

`TutorRequest.language` accepts `telugu`, `english`, or `mixed`; a supplied mode overrides the stored preference for that turn. VoiceTutor also updates the authenticated student's saved language preference when the selector changes and records the active mode in the session voice checkpoint. Telugu responses use Telugu Unicode script. Mixed responses use Telugu script for Telugu words and retain English technical terms. Transcript text is passed through without romanization or technical-term rewriting; recorded audio uses Prisma's existing `indic-auto`/`codemix` configuration.

## Interruption and state

`session_voice_states` is keyed by the owned learning session and cascades on session deletion. It stores the current topic through the authoritative session, lesson-step label, student question, response language, playback state, latest voice transcript, assistant-message/time checkpoint, resume status, and update time. The authenticated `GET/PUT /api/v1/voice/sessions/{session_id}/state` routes reuse the standard ownership check and reject checkpoints outside the session.

VoiceTutor cancels browser speech requests, stops the media element immediately, and invalidates the `AvatarSyncController` generation. A late play/pause/end event is ignored unless the media element still reports the corresponding current state. Asking a question sends it to the existing session tutor with its saved topic/history. The UI offers a separate resume confirmation and seeks the saved reply audio to the saved media time only after confirmation. Audio timing uses the media element clock; any mouth animation without provider alignment is labeled approximate.

Voice API requests carry a UUID `X-Request-ID`; the backend validates or replaces it and returns it in the response header. Browser cancellation aborts in-flight STT/TTS fetches, while provider calls retain their configured bounded timeouts.

Per-student process-local limits cap STT at 10 calls/minute and TTS at 20 calls/minute, returning HTTP 429 with `Retry-After`. Deployments with multiple workers should move this counter to their shared rate-limit service.

## INT19 avatar contract

`frontend/src/immersiveVoiceBridge.ts` exports `immersiveVoiceBridge`, `ImmersiveVoiceBridge`, and the stable state union `idle | listening | thinking | speaking | paused | interrupted | error`. Integrators can subscribe to state changes and avatar frames with `subscribe` / `subscribeFrames`, read the current event with `getState` / `getFrame`, publish explicit states with `setState`, and pass media-clock `AvatarSyncFrame` values with `acceptFrame`. Older generations are discarded. Provider visemes/phonemes can be passed through the existing `AvatarSyncController`; INT-20 adds no provider cues.

## Verification

Automated tests use deterministic provider doubles. No live provider requests are part of test or browser workflows. Playwright output is directed to an INT-20-specific temporary directory. Run the backend tests, `npm test`, `npm run build`, and the `int-20-voice-interruption.spec.ts` Playwright workflow to reproduce local checks.
