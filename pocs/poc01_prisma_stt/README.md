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

Open `.env`, set your key and **verified** GNANI Prisma STT HTTPS endpoint from the GNANI developer portal. Never paste your key into chat.

## Tests

```powershell
python -m pytest -q
```

## Live experiment

Record a clear mono PCM WAV file (suggested 16 kHz, 16-bit, 5–15 seconds, max 30 seconds). Example sentence:

“Hello, nenu DSA nerchukuntunnanu. Can you explain what is an algorithm?”

```powershell
python run.py .\sample.wav
```

Sample audio files are ignored by Git. Review accuracy for Telugu words, English technical terms, code-switching, and missing words. Test at least three clips: Telugu, English, and mixed.

## API compatibility note

**Do not assume the request schema is confirmed.** This POC uses a generic multipart POST with `file`, `language`, and `format` fields and `X-API-Key-ID` header as initial integration assumptions. GNANI may require different fields, authentication or response keys for your enabled Prisma version. Check the account-specific API documentation and adjust only this adapter. The project deliberately does not hardcode an unverified endpoint.

## Acceptance checklist

- [ ] Offline tests run successfully
- [ ] Live GNANI call succeeds
- [ ] Telugu speech transcript reviewed
- [ ] English speech transcript reviewed
- [ ] Mixed Telugu–English transcript reviewed
- [ ] Failures and latency documented

Only after acceptance should POC-01 be marked complete.
