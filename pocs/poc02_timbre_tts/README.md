# POC-02 — GNANI Timbre v2.5 Text-to-Speech

REST endpoint: `POST https://api.vachana.ai/api/v1/tts/inference`.
Authentication: `X-API-Key-ID`. JSON request; successful response is binary WAV.
Based on user-provided official [GNANI REST docs](https://docs.gnani.ai/api/TTS/tts-inference.md)
and [voice catalog](https://docs.gnani.ai/api/TTS/available-voices.md).

## Windows CMD quick start

```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
git pull
cd pocs\poc02_timbre_tts
python -m pip install -r requirements.txt
if not exist .env copy .env.example .env
notepad .env
python -m pytest -q
python run.py "Hello, welcome to BHASHALEARN AI." --language en-IN --output english.wav
python run.py "నమస్కారం! భాషా లెర్న్ ఏఐకి స్వాగతం." --language te-IN --output telugu.wav
```

Copy your *working* POC-01 key into the local POC-02 `.env` file; never
share or commit it. If your Windows terminal has trouble with Telugu text,
save this command in a UTF-8 script or use Windows Terminal.

Play results by double-clicking the WAV files, or run:
```cmd
start english.wav
start telugu.wav
```

English defaults to **Kaveri** (`en-IN`); Telugu defaults to **Suhana**
(`te-IN`). Use `--voice` to override, e.g. `--voice Lavanya` for Telugu.
Use `--language auto --voice Suhana` to experiment with mixed text.

## Verification (2026-11-04)

The tests mock GNANI; they do not call the paid API. A live request needs
an API key with TTS scope and available credits. The adapter validates
the response Content-Type and saves only valid, nonempty WAV data.
If a request fails, the CLI reports a safe error without printing your key.

### Results from the current environment (2026-11-04)

- Offline tests: **13 passed** from the repository root and **13 passed** from
  this POC directory using the POC `.venv`.
- `.env` loading: the CLI loads `Path(__file__).with_name(".env")`, which is
  `pocs/poc02_timbre_tts/.env`; its `GNANI_API_KEY` setting is non-empty. The
  value is intentionally not recorded here.
- Authentication contract: `X-API-Key-ID` and
  `https://api.vachana.ai/api/v1/tts/inference` match Gnani's official client
  documentation.
- Live English (`en-IN`): **success**, 353,324 bytes saved to
  `pocs/poc02_timbre_tts/artifacts/english.wav`.
- Live Telugu (`te-IN`): **success**, 568,364 bytes saved to
  `pocs/poc02_timbre_tts/artifacts/telugu.wav`.
- Audio validation: both files are mono, 48 kHz, 16-bit PCM WAVs with nonzero
  frames. The response used placeholder `0xffffffff` RIFF/data lengths, so the
  two local output headers were corrected to match their actual file sizes for
  standard WAV readers. The audio payload was not changed.
- Offline tests: **13 passed** from both the repository root and this POC
  directory using the POC `.venv`.

The test module supports pytest launched from either the repository root or
this POC directory.

Acceptance:
- [x] REST request/response fields matched to provided official documentation
- [x] English/Telugu synthesis implementation and CLI
- [x] Offline unit tests authored
- [x] Offline tests executed (13 passed from both supported working directories)
- [x] Live English audio generated and WAV structure validated
- [x] Live Telugu audio generated and WAV structure validated
- [ ] Latency and audio quality reviewed
