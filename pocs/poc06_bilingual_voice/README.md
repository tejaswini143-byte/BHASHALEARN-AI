# POC-06 — Full Bilingual Voice Interaction

POC-06 connects PCM WAV or optional microphone input to the existing Gnani
Prisma STT, Gemini bilingual Tutor, POC-04 adaptive engine, POC-05 shared
session, and Gnani Timbre TTS. Provider calls are synchronous and every result
reports the stages that completed, stage latencies, context, and structured
errors. The offline simulation and tests use injected fake provider clients;
they do not establish live provider success.

## Reused interfaces and verified contracts

| Component | Existing interface reused | Contract used here |
| --- | --- | --- |
| POC-01 Prisma | `PrismaSTTAdapter(PrismaConfig).transcribe(path) -> Transcript` | `POST https://api.vachana.ai/stt/v3`; `X-API-Key-ID`; multipart `audio_file`; form `model=prisma-v3.0`, `language_code=indic-auto`, `format=codemix`; result has `text`, optional language and raw JSON. |
| POC-02 Timbre | `TimbreTTSAdapter(TimbreConfig).synthesize(text, language, voice)` and `write_audio(bytes, path)` | `POST https://api.vachana.ai/api/v1/tts/inference`; `X-API-Key-ID`; binary WAV response; English `en-IN`/Kaveri, Telugu `te-IN`/Suhana, 48 kHz mono 16-bit PCM. POC-06 uses these two verified language/voice pairs. |
| POC-03 Gemini | `LLMClient.complete`, `Tutor.ask`, `Tutor.set_language`, `Tutor.set_level`, existing prompt/history | The same `LLMClient` instance is supplied to the POC-03 `Tutor` and POC-04 structured evaluator through POC-05. POC-06 does not create a second conversation history. |
| POC-04 adaptation | `StudentState`, `AdaptiveTeachingEngine.submit_answer`, `adaptive_instruction` | Objective questions use the existing deterministic evaluator; open responses use POC-04's validated structured LLM evaluation. The engine updates the state held by POC-05. |
| POC-05 session | `SessionManager`, `SharedSessionRuntime.voice_transcript`, `adaptive_answer`, `switch_language`, `get_teaching_context` | Transcripts and tutor replies enter the same bounded session history; identity, language, topic, mastery, difficulty, and hints remain in the existing shared context. |

POC-01's own audio validation accepts uncompressed PCM `.wav`, rejects empty
audio, limits files to 10 MB and duration to 30 seconds, and does not itself
enforce sample rate/channel count. Its README suggests mono, 16 kHz, 16-bit PCM
for bilingual clips. POC-06 microphone recording defaults to that suggestion;
WAV file input follows POC-01 validation rather than inventing extra Prisma
format restrictions.

## Architecture

```text
Microphone (optional) / PCM WAV file
              |
              v
     POC-01 validate + Prisma STT adapter
              |
              v
 POC-05 SharedSessionRuntime -> POC-03 Tutor / Gemini
              |                         |
              +-> POC-04 adaptive state + strategy
                                        |
                                        v
                          POC-02 Timbre adapter -> WAV
```

POC-03's system prompt defines the language contract for every tutor call:
English mode responds in English; Telugu mode uses Telugu Unicode script; mixed
mode keeps Telugu words in Telugu script and English terms in Latin script,
without Romanized Telugu or word-by-word code switching. The prompt also applies
to initial explanations, follow-ups, hints, corrections, and practice. As with
all LLM instructions, this guides output but cannot guarantee every generated
sentence is linguistically correct.

`VoicePipeline` accepts a session ID, WAV path, optional language override, and
optional practice question/rubric. With a question, the recognized speech is
evaluated and updates mastery only when POC-04 returns a scored evaluation.
Without one, it is a voice-transcript question or follow-up. The pipeline does
not retry paid provider requests automatically. STT/TTS timeout errors mark
whether a stage-only retry is safe; `synthesize_saved_response` retries TTS
from retained text without re-running STT, Gemini, or mastery updates.

POC-06 constructs the TTS wrapper from the existing `TimbreConfig`; it does
not wrap an already constructed client as a config. The wrapper sanitizes
common Markdown and LaTeX display syntax for speech. For mixed Telugu/English,
it splits text by Telugu and Latin script and sends each segment using the
POC-02 verified `te-IN`/Suhana or `en-IN`/Kaveri pairing, then concatenates PCM
frames when response formats match. It does not use POC-02's experimental
`auto` mixed-text mode. This fallback may have a noticeable join between
languages; Latin transliteration of Telugu is synthesized as English. A custom
`GNANI_TTS_VOICE` override is rejected for mixed sessions because one voice
has not been validated across both language modes.

TTS errors include a safe error category and exception class; HTTP status is
included when available. Raw request text, response bodies, API keys, and
headers are not included in diagnostics. HTTP 400 errors report a general
request-rejected category because provider detail text could contain submitted
content.

The result includes transcript and raw Prisma response, tutor text, topic,
language, difficulty, mastery, adaptive strategy, WAV path/format/duration,
per-stage latency (`audio_validation`, `stt`, `tutor`, `tts`, `total`), and
structured stage errors. If TTS fails, the successful transcript and tutor
response remain in the result. Empty audio/transcripts and empty/failed tutor
responses do not trigger later provider stages or speech generation.

## Setup

Use the existing POC-01/02/03 local `.env` files, or create an optional local
`pocs\poc06_bilingual_voice\.env` from `.env.example` to provide non-placeholder
overrides. Provider values are loaded into process memory only; no credentials
are logged. The root `.gitignore` ignores `.env` files and WAV outputs. Do not
commit generated recordings.

```cmd
cd /d C:\Users\Tejaswini\BHASHALEARN-AI
python -m pip install -r pocs\poc06_bilingual_voice\requirements.txt
```

Optional microphone capture requires `sounddevice` and a working input device:

```cmd
python -m pip install sounddevice
```

Without it, use `/file <path.wav>`. Recording settings are `POC06_SAMPLE_RATE`
(16000), `POC06_CHANNELS` (1), `POC06_RECORDING_SECONDS` (5), and
`POC06_MAX_RECORDING_SECONDS` (30). Output directory defaults to
`pocs/poc06_bilingual_voice/artifacts`.

## CLI

```cmd
python pocs\poc06_bilingual_voice\run.py
```

Choose student ID, language (`english`, `telugu`, `mixed`), and topic. Commands:

| Command | Action |
| --- | --- |
| `/start` | Begin or continue a lesson in the current shared session. |
| `/topic fractions` | Set topic and teach it. Other topics use structured open-answer evaluation. |
| `/language telugu` | Switch future tutor and speech output language; `english` and `mixed` are also supported. |
| `/record` | Record a short microphone WAV (optional dependency). |
| `/file path_to_audio.wav` | Transcribe a WAV as a question or follow-up. |
| `/answer path_to_audio.wav` | Transcribe and evaluate speech against the current practice question. |
| `/context` | Display topic, language, difficulty, mastery, hint count, and strategy. |
| `/reset` | Reset learning evidence and history while retaining session ID, student, topic, and language. |
| `/end` or `/quit` | End the current session. |

By default, successful WAV output is saved and played with Windows `winsound`.
Use `--save-only` to save without playback. User-selected input files are not
copied. Microphone audio is written to the operating system temporary folder
and deleted after processing.

When language changes with `/language`, the same session and mastery remain;
the next tutor response uses the new mode and the displayed practice question
is refreshed in the selected language. For fractions, the choices and accepted
numeric answers remain the same in English, Telugu, and mixed mode. The initial
lesson prompt includes that exact practice question so the tutor's explanation
and answer evaluator stay aligned.

## Prisma Telugu/English recognition evaluation

POC-01 sends `model=prisma-v3.0`, `format=codemix`, and a `language_code` to
`POST /stt/v3`. POC-06 microphone defaults to mono, 16 kHz, 16-bit PCM. POC-01
validates PCM WAV, non-empty audio, the 10 MB size limit, and the 30-second
duration limit, but its validator does not reject other PCM sample rates or
channel counts. For repeatable samples, use clear mono, 16 kHz PCM recordings
longer than 3 seconds; clip-specific acceptance is still determined by the
measured output, not model claims.

The current POC-01 auto configuration is `indic-auto`; explicit documented
codes are `en-IN` and `te-IN`. The repeatable evaluation script uses explicit
English and Telugu codes and `indic-auto` for the mixed sentence. `codemix`
preserves language scripts. Prisma v3 provider material describes Telugu and
English coverage, automatic language identification, and code-mixed speech;
the exact recordings below must still be reviewed for BHASHALEARN's sentences.
[Gnani Prisma v3 overview](https://www.gnani.ai/resources/prisma-v3),
[Prisma v3 model notes](https://www.gnani.ai/resources/blogs/prisma-v3-0-speech-recognition).

Record three separate WAV files containing the printed sample sentences, then
run:

```cmd
python -m pocs.poc06_bilingual_voice.evaluate_transcription --english pocs\poc06_bilingual_voice\artifacts\english.wav --telugu pocs\poc06_bilingual_voice\artifacts\telugu.wav --mixed pocs\poc06_bilingual_voice\artifacts\mixed.wav
```

For each clip the script reports the exact expected phrase, raw Prisma
transcript (unchanged; no Gemini rewrite), detected language, language code,
format, WAV properties, latency, Unicode-token WER, and whitespace-normalized
Unicode-code-point CER. Save these local recordings securely; they are not
committed. Short exact phrases produce noisy error-rate estimates, so listen to
the recordings and review every transcript in addition to reading WER/CER.

## Live language and voice check

With the POC `.env` files available and `sounddevice` installed, start:

```cmd
python -m pocs.poc06_bilingual_voice.run --save-only
```

Select `telugu` and record `మిశ్రమ భిన్నం అంటే ఏమిటి?`; switch using
`/language english` and record `What is a mixed fraction?`; then switch to
`/language mixed` and record `Mixed fraction అంటే ఏమిటి? ఒక example చెప్పండి.`
For each turn check the raw transcript, mode, tutor language, TTS error or
generated WAV path, and latency. Ask a follow-up by `/record`, then use
`/context` to confirm the topic, mastery, and difficulty persist. The
`--save-only` option suppresses automatic playback; open each printed WAV path
in an audio player and verify it is audible. These checks need to be performed
on real clips; the script and offline tests do not claim live accuracy.

## Speech-text preparation

Timbre receives a deterministic speech-only rendering while the original tutor
response stays unchanged in the result and conversation history. POC-06 removes
common Markdown headings, emphasis, links, list markers, and code fences;
converts `1/2` to “1 over 2”, `2 1/4` to “2 and 1 over 4”, and common TeX
fractions/operators to words; and preserves Telugu Unicode. It does not
transliterate text. Mixed speech uses separate validated `en-IN`/Kaveri and
`te-IN`/Suhana requests split by script, then joins PCM frames when formats
match. This can sound discontinuous at language boundaries and does not detect
Telugu written in Latin transliteration.

## Offline simulation and tests

The simulation uses the real pipeline/adapters with mocked Prisma, Gemini, and
Timbre clients. It walks through mixed-language fractions, an incorrect answer
and hint, a corrected answer, a voice follow-up, shared-context verification,
WAV creation, and session end without network access.

```cmd
python -m pocs.poc06_bilingual_voice.simulate
python -m pytest -q pocs\poc06_bilingual_voice\tests
python -m pytest -q pocs\poc01_prisma_stt\tests pocs\poc02_timbre_tts\tests pocs\poc03_bilingual_llm\tests pocs\poc04_adaptive_teaching\tests pocs\poc05_shared_session_context\tests pocs\poc06_bilingual_voice\tests
```

The POC-06 suite covers WAV validation and cleanup, language mapping, Prisma
transcript normalization and failures, Tutor/context continuity, adaptive
updates, isolation, session termination, Timbre output/failures, latency,
partial success, and invalid-audio short circuiting.

### Verification status

- POC-06 baseline checks: user reported **123 tests passed** before the Telugu
  prompt, STT evaluation, and speech-formatting changes in the current working
  revision. Re-run the suites below for this revision; this Codex environment
  currently has no usable Python interpreter. The repository venv launcher
  refers to a missing Python 3.12 installation, and `uv` could not download a
  replacement because sandbox network access is blocked.
- POC-01: implementation uses the documented Prisma request fields and
  existing tests, but its README acceptance checklist does not record a live
  STT call or reviewed English/Telugu/mixed clips.
- POC-02: its README records 14 offline tests and live English and Telugu WAV
  generation. It records three-request sample latencies: English 4.190, 1.767,
  1.636 seconds; Telugu 2.215, 3.204, 3.178 seconds. Mixed-language TTS and
  subjective speech quality remain unverified.
- POC-03: its README records 11 offline tests and basic Gemini CLI responses
  from normal Windows CMD. Dedicated Telugu, mixed, follow-up, and language
  switching checks remain pending there.
- POC-04: Windows CMD reported 28 passed in 0.11 seconds and the three learner
  simulations completed with the supplied results.
- POC-05: Windows CMD reported 22 passed in 0.05 seconds and the supplied
  chat-to-simulated-voice walkthrough completed with 50% mastery and 8 turns.
- POC-06 live microphone, Prisma transcript, Gemini tutor, and shared context:
  the user reported success in the mixed-language CLI session on 2026-11-05.
- POC-06 live Timbre stage in that session: **failed before a provider request**.
  The reported generic error and 0.000 s TTS latency are consistent with the
  verified factory argument mismatch described below. No provider HTTP error
  or provider response was observed in that run.
- POC-06 live TTS, Telugu response script quality, and the three-clip STT
  evaluation for this revision: **not yet verified**. Run the live checklist
  and inspect the generated WAV and raw transcripts before acceptance.

## Known limitations

- This POC has not established live Prisma transcription or end-to-end voice
  quality. POC-01 uses `indic-auto` plus `codemix`; actual English, Telugu, and
  code-switching accuracy needs reviewed live clips.
- Mixed Timbre output is assembled from separate verified English and Telugu
  synthesis requests; the joined audio and naturalness still need live review.
- Microphone recording depends on optional `sounddevice`, hardware, and OS
  permissions. PCM WAV is the portable fallback.
- The system is synchronous and in-memory. There is no streaming audio,
  persistent storage, authentication, diarization, or user recording library.
- Automatic playback uses Windows `winsound`; saved WAVs can be played in any
  compatible audio player.
- Provider timeouts are surfaced, not automatically retried. Retry TTS from
  saved tutor text to avoid repeating STT, LLM evaluation, or mastery updates.

## TTS integration debugging note

The initial POC-06 CLI passed `TimbreTTSAdapter(timbre_config)` into
`TimbreSpeechAdapter.from_config`, whose contract expects the `TimbreConfig`
itself. The wrapper then treated the client object as configuration; accessing
its `voice` attribute raised `AttributeError` before the network request. A
catch-all converted that local integration bug into the unhelpful generic
`provider_error`. POC-06 now passes the config directly and reports safe
exception type, HTTP status when available, and category. Regression tests
cover the old incorrect factory call and the corrected construction; live
verification is still required.

