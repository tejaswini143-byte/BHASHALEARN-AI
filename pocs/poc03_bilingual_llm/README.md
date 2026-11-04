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

### Executed results

- Repository root: `11 passed` using the POC-02 virtual environment and
  `python -m pytest -q pocs/poc03_bilingual_llm/tests`.
- POC directory: `11 passed` using the same environment and
  `python -m pytest -q tests`.
- Live English, Telugu, and mixed provider demonstrations: **not run**. No
  `pocs/poc03_bilingual_llm/.env` exists and the process environment has no
  `LLM_API_KEY`. Add a provider-authorized key to the local POC `.env` to
  enable live evaluation. No Gnani speech key was treated as LLM access.
- Test results prove orchestration and prompt construction with a deterministic
  fake provider. They do not prove live translation quality or teaching quality.

## Limitations

- Live provider responses depend on configured account access, model, and
  provider compatibility; no live success is assumed by this implementation.
- Conversation state is in memory, limited to recent turns, and disappears
  when the CLI exits.
- Language output quality and teaching accuracy need human review.
- There is no streaming, retrieval, persistent learner profile, or shared
  session service in this POC.
