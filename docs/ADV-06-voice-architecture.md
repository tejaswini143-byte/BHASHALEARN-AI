# ADV-06 Gnani Live Voice Classroom

## Audited contracts

- Voice Studio captures up to 30 seconds, converts mono audio to PCM WAV at 16 kHz, requests microphone permission only on an explicit user action, and releases tracks after recording. The learner can stop capture, review/edit the transcript, type instead, submit to the existing tutor chat endpoint, and play or stop returned audio.
- The authenticated REST routes are `POST /api/v1/voice/sessions/{session_id}/transcribe` and `/speech`. Chat persistence remains on the existing tutor session route. Voice audio is not persisted.
- Prisma's recorded official REST contract is `POST https://api.vachana.ai/stt/v3`, `X-API-Key-ID`, multipart field `audio_file`, and form fields `model=prisma-v3.0`, `language_code=indic-auto`, `format=codemix`. The recorded short-clip maximum is 30 seconds; the local adapter validates nonempty PCM WAV up to 10 MiB. The response is JSON with `transcript` (or the adapter's compatible `text` field), optional `detected_language_code`/`language`, `request_id`, timing fields, and optional `truncated`. `indic-auto` plus `codemix` is the configured selector; English, Telugu, and code-switch accuracy still requires live reviewed clips.
- Timbre's recorded official REST contract is `POST https://api.vachana.ai/api/v1/tts/inference`, `X-API-Key-ID`, JSON fields `text`, `voice`, `model=timbre-v2.5`, `language`, `speed`, and `audio_config` (`sample_rate=48000`, `num_channels=1`, `sample_width=2`, `encoding=linear_pcm`, `container=wav`), followed by binary WAV. Verified language/voice pairs are English `en-IN`/Kaveri and Telugu `te-IN`/Suhana. Mixed speech is segmented and joined by the existing POC-06 adapter.
- Official source URLs recorded by the existing POCs: [Prisma STT](https://docs.gnani.ai/api/STT/speech-to-text.md), [Timbre inference](https://docs.gnani.ai/api/TTS/tts-inference.md), and [available voices](https://docs.gnani.ai/api/TTS/available-voices.md). The docs site did not return accessible content during this task; request formats above are corroborated by the repository's existing adapters and prior POC verification notes.

## Transport and event contract

`frontend/src/voiceContract.ts` defines a provider-neutral `VoiceTransport`, typed recognition events (started, partial/final transcript, failure), synthesis and playback events, cancellation, error categories, and teacher bridge messages. `MockVoiceTransport` emits deterministic mixed Telugu/English transcript text and a mock WAV URL for offline development. The current production REST calls remain in Voice Studio and do not emit partial transcripts or streaming audio.

Errors distinguish permission denial, unsupported browser capability, no speech, network/provider failure, invalid audio, and user interruption. An `AbortSignal` is the transport cancellation boundary. Playback start/end/interruption carries the audio artifact and drives teacher states. A board command carries normalized `[0,1]` coordinates and is validated through ADV-05's `pointAt` action.

## ADV-05 teacher integration boundary

Playback start drives the existing `explain` teacher state; playback end/interruption returns it to `idle`. The `speak` action is emitted only if a future provider/alignment service supplies a validated viseme timeline. Current Timbre REST returns WAV bytes without timing metadata, so generated audio is not lip-synced. Smartboard commands map to existing `pointAt` actions; this contract does not claim that Gnani generates lesson commands.

## Connectivity status

The repo's POC-02 report records successful live English and Telugu Timbre WAV generation (2026-11-04); those artifacts still exist in the original project worktree and their mono 48 kHz/16-bit WAV metadata was rechecked read-only. This audit did not repeat those paid calls or assess the audio by listening. POC-01 does not record an accepted live Prisma transcript for English, Telugu, or mixed speech. Non-placeholder Gnani API-key and endpoint settings are present in original-project POC-01/POC-02 local `.env` files; the values were not displayed or validated. The RC/recovery environment has no Gnani config. No current provider call was approved or made, so this does not establish current live Prisma connectivity or end-to-end live classroom acceptance. REST is documented; streaming/websocket APIs were not found in the official materials recorded here and are not assumed.

## Verification

Focused browser-independent voice contract tests are in `frontend/tests/voice-contract.test.mjs`. Result: **3 passed**. `npm.cmd run build` completed successfully; Vite reported an existing large-chunk advisory for Three.js assets. Mock results validate the interface and deterministic behavior only; they do not establish provider connectivity, browser microphone permission, audio quality, or lip sync.
