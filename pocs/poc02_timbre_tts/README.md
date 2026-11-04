# POC-02 — GNANI Timbre v2.5 TTS

Goal: synthesize short English and Telugu explanations for BHASHALEARN AI.

**Status: scaffold only.** The supplied GNANI introduction confirms Timbre v2.5
and the `X-API-Key-ID` authentication header, but not the TTS REST request body,
voice identifiers, endpoint path, or response encoding. Do not guess these.

## Setup (Windows CMD)

```cmd
cd pocs\poc02_timbre_tts
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python -m pytest -q
```

Do not commit or paste API keys into chat. The existing POC-01 HTTP 401 must be
resolved before assuming the key is valid for TTS.

## Documentation needed

Please provide the cURL/Python example and success response details from
https://docs.gnani.ai/api/TTS/tts-inference.md and one voice ID from
https://docs.gnani.ai/api/TTS/available-voices.md.

Once verified, implement request encoding, audio decoding, playback and
integration tests. Verify one English and one Telugu utterance with real GNANI
responses before marking complete.

## Acceptance
- [ ] Official request/response schema verified
- [ ] Offline tests executed
- [ ] English speech synthesized and reviewed
- [ ] Telugu speech synthesized and reviewed
- [ ] Voice ID and output format recorded
- [ ] Errors/latency recorded
