# POC-01 — GNANI Prisma STT

**Purpose:** prove Telugu–English speech recognition before integrating voice into the BHASHALEARN AI teaching engine.

## Architecture

`PCM WAV audio → validation → PrismaSTTAdapter → Transcript → future session/teaching engine`

This is a standalone proof of concept, not the production backend.

## Windows setup (PowerShell)

```powershell
cd pocs/poc01_prisma_stt
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and set your API key. The documented endpoint is already configured. Never paste your key into chat.

## Tests

```powershell
python -m pytest -q
```

## Live experiment

For the first English smoke test, download the generated `poc01_sample_speech.wav` from the ChatGPT conversation and save it in this folder as `sample.wav`. It is synthetic English speech (22.05 kHz mono PCM, approximately 8.2 seconds), so it checks the upload/transcription pipeline, **not** Telugu–English recognition quality.\n\nFor the later bilingual acceptance test, record a clear mono PCM WAV file (suggested 16 kHz, 16-bit, 5–15 seconds, max 30 seconds). Example sentence:

“Hello, nenu DSA nerchukuntunnanu. Can you explain what is an algorithm?”

```powershell
python run.py .\sample.wav
```

Sample audio files are ignored by Git. Review accuracy for Telugu words, English technical terms, code-switching, and missing words. Test at least three clips: Telugu, English, and mixed.

## Confirmed from GNANI API introduction

- Base URL: `https://api.vachana.ai`
- API key header: `X-API-Key-ID`
- Prisma v3 model selector: `prisma-v3.0`
- REST short-clip limit: 30 seconds

## Confirmed REST request schema

- `POST https://api.vachana.ai/stt/v3`
- Header: `X-API-Key-ID`
- Multipart file: `audio_file`
- Form fields: `model=prisma-v3.0`, `language_code=indic-auto`, `format=codemix`
- Response: `transcript`, optional `detected_language_code`, `request_id`, timings, and optional `truncated`
- A successful empty transcript (`""`) means no speech was detected, not an API error.

Source: https://docs.gnani.ai/api/STT/speech-to-text.md

## Acceptance checklist

- [ ] Offline tests run successfully
- [ ] Live GNANI call succeeds
- [ ] Telugu speech transcript reviewed
- [ ] English speech transcript reviewed
- [ ] Mixed Telugu–English transcript reviewed
- [ ] Failures and latency documented

Only after acceptance should POC-01 be marked complete.
