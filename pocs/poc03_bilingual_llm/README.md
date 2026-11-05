# POC-03 — Bilingual LLM Teaching

An interactive Telugu-English teaching proof of concept. The tutor adapts its
prompt to English, Telugu, or mixed teaching, and beginner, intermediate, or
advanced level. It keeps a bounded, in-memory message history for follow-up
questions. This is per-process CLI state, not persistent student memory.

## Architecture

```text
CLI -> Tutor -> teaching prompt + bounded conversation -> LLMClient
                                                  -> configurable OpenAI-compatible chat completions API
```

`LLMClient` is provider-independent at the HTTP contract level: configure the
HTTPS chat-completions URL and model for any provider that implements the
OpenAI-compatible `{model, messages}` request and
`choices[0].message.content` response. POC-03 does not reuse `GNANI_API_KEY`;
LLM credentials are configured separately as `LLM_API_KEY`.

## Windows CMD setup

```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI\pocs\poc03_bilingual_llm
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
python -m pytest -q
python run.py
```

Put an authorized LLM API key in the local `.env`. Never commit `.env`. A
Gnani STT/TTS key does not imply LLM access. If no authorized provider key is
available, deterministic mock-provider tests still run offline; live teaching
cannot be validated until a provider key and access are configured.

## Environment

| Variable | Purpose | Default |
| --- | --- | --- |
| `LLM_API_KEY` | Dedicated LLM provider key | required |
| `LLM_BASE_URL` | HTTPS OpenAI-compatible chat completions endpoint | `https://api.openai.com/v1/chat/completions` |
| `LLM_MODEL` | Provider model identifier | `gpt-4o-mini` |
| `LLM_TIMEOUT_SECONDS` | Request timeout | `45` |

The CLI loads `.env` next to `run.py`.

## CLI use

```text
BhashaLearn POC-03 — /language english|telugu|mixed, /level beginner|intermediate|advanced, /quit
You: Explain fractions with an example
Teacher: ...
You: /language telugu
You: ఒక భిన్నంలో హారం అంటే ఏమిటి?
Teacher: ...
You: /level advanced
You: How does a rational number relate to a fraction?
You: /quit
```

Supported controls: `/language english|telugu|mixed`,
`/level beginner|intermediate|advanced`, `/quit`. Changes affect subsequent
responses while retaining the recent conversation history.

## Teaching behavior

The system prompt requests simple or deeper instruction by level, steps,
worked examples, brief understanding checks, contextual follow-ups, and kind
corrections. It directs the teacher to use a hint or question before revealing
an answer during guided practice. These are model instructions, not guaranteed
pedagogical outcomes; live quality requires review.

## Test scenarios and results

Offline tests cover English, Telugu script, mixed-language prompting, level
adaptation, switching languages, follow-up context, guided practice and
correction instructions, bounded history, missing credentials, and provider
errors.

### Live Gemini verification (2026-11-05)

- The local `pocs/poc03_bilingual_llm/.env` was present and readable. Its
  `LLM_API_KEY` value was present (the value was not displayed); the configured
  endpoint host was `generativelanguage.googleapis.com`, model was
  `gemini-3.5-flash-lite`, and timeout was 60 seconds. Git confirmed that this
  `.env` is ignored and is not tracked.
- Google's Gemini model catalog lists `gemini-3.5-flash-lite` as a stable
  Gemini API model. This confirms the model ID exists in the catalog, but the
  account's access could not be confirmed. The configured model was not changed.
- A direct live English connectivity request failed before a response with the
  exact client error `Unable to connect to the remote server`. The environment
  therefore did not establish Gemini API connectivity. No response was
  received, so live English teaching, follow-up/context, Telugu, mixed-language
  teaching, language switching, and response latency remain unverified.
- This shell had no `python` executable on `PATH`. The existing POC-02 virtual
  environment could not start because its base Python executable returned
  `Access is denied`. Provisioning an isolated Python with `uv` also failed:
  the sandbox denied the download connection with `tcp connect error` and
  Windows socket error `10013`. Consequently, the POC-03 pytest suite was not
  run in this verification session, and the app's `python-dotenv` loader was
  not executable here. The `.env` file's values were read and checked without
  displaying the key.
- An earlier run recorded 11 passing offline POC-03 tests for orchestration
  and prompt construction using a deterministic fake provider. Those results
  do not establish live Gemini connectivity or translation and teaching quality.

## Limitations

- Live provider responses depend on configured account access, model, and
  provider compatibility; no live success is assumed by this implementation.
- Conversation state is in memory, limited to recent turns, and disappears
  when the CLI exits.
- Language output quality and teaching accuracy need human review.
- There is no streaming, retrieval, persistent learner profile, or shared
  session service in this POC.

### Windows CMD verification (2026-11-05)

- Python 3.12.10 was available in normal Windows CMD.
- POC-03 automated tests passed: 11 passed in 0.47 seconds.
- Google's Gemini API endpoint was reachable from Windows CMD.
- The POC-03 interactive CLI successfully generated live Gemini responses to the inputs `hlo` and `english , telugu , hindi`.
- These results confirm basic live LLM connectivity and response generation outside the Codex sandbox.
- The earlier connectivity and Python execution failures were specific to the Codex sandbox environment.
- Dedicated English, Telugu, mixed-language, follow-up/context, language-switching, and response-latency evaluations remain pending.
- The Gemini API key was not displayed or committed.