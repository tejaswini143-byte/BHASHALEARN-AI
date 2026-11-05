# POC-05 — Shared Session Context

POC-05 keeps one bounded, in-memory learner session across bilingual chat,
adaptive answers, simulated voice transcripts, and future visual lesson events.
It composes POC-04's `StudentState` rather than copying identity, topic,
language, difficulty, answers, hint count, or mastery into a second model.

## Architecture

```text
Chat / simulated voice / visual event
                 |
                 v
      SessionManager -> SessionStore protocol -> InMemorySessionStore
                 |
                 +-> SessionContext -> POC-04 StudentState (canonical progress)
                 |
                 +-> SharedSessionRuntime -> POC-03 Tutor -> POC-03 LLMClient
                                      |
                                      +-> POC-04 AdaptiveTeachingEngine
```

`SessionStore` is the persistence seam for a future PostgreSQL adapter. The
manager owns lifecycle and progress updates. `SharedSessionRuntime` reuses the
existing POC-03 `Tutor` and POC-04 evaluator, strategy rules, and state model.
Before each Tutor call, its short-lived `history` cache is rebuilt from the
manager's conversation events; the manager's history is the source of truth.

## Session data and lifecycle

Each `SessionContext` contains a `StudentState` plus one bounded event list,
lesson objective, current teaching step, selected adaptive strategy, and
created/updated/activity/reset/end timestamps. Session ID, student ID, topic,
language, difficulty, recent answers, counts, hint use, and mastery are exposed
as properties from the single `StudentState`.

`SessionManager` supports create, retrieve, update, reset, end, recent-session
and recent-turn listing, progress callbacks, and a compact teaching-context
snapshot. Reset clears the conversation and learning evidence, returns to
beginner with 50% prior mastery, and retains the session ID, student, topic,
and language by default. Ended sessions remain readable but reject updates.
Recent conversation events are capped (24 by default); POC-03 receives at most
its configured message history. Separate session objects isolate students.

Conversation turns carry a modality: `chat`, `voice_transcript`,
`adaptive_tutor`, or `visual_lesson`. Voice input is a supplied transcript only;
no speech recognition or synthesis is implemented. Visual events can be
stored with metadata, but are not forwarded as text history or processed as
images.

## CLI

From Windows CMD:

```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
python -m pytest -q pocs\poc05_shared_session_context\tests
python -m pocs.poc05_shared_session_context.simulate
python pocs\poc05_shared_session_context\run.py
```

The CLI loads the existing `pocs\poc03_bilingual_llm\.env` without printing
credentials. Choose a student, language, and topic. Use `/answer <text>` for
the current objective question, `/voice <transcript>` to simulate voice,
`/language english|telugu|mixed` to switch language, `/visual <description>`
to record a future visual event, `/context` to inspect shared state, `/reset`
to reset, and `/end` to end the session. Ordinary text is sent as chat.

## Offline demonstration

`simulate.py` uses a fake POC-03 provider and deterministic objective evaluator;
it makes no Gemini requests. Its walkthrough creates a mixed-language fractions
session, gives an incorrect answer and receives a hint, accepts a corrected
answer, switches to a simulated voice follow-up, checks history and learner
state continuity, and ends the session. This script is authored but has not
been executed in the current sandbox.

## Test results

- POC-05: **22 deterministic test cases authored; not run in this Codex
  sandbox**. Run the command above from normal Windows CMD and record the actual
  pass/fail count here before commit.
- POC-04 validation prerequisite: Windows CMD reported **28 passed in 0.11s**;
  its three-profile simulation reported Student A at 29% mastery with an
  intermediate-to-beginner change and prerequisite review, Student B at 69%
  with beginner-to-intermediate promotion and practice, and Student C at 80%
  with intermediate-to-advanced promotion and challenging practice.
- POC-03 dedicated Telugu, mixed, follow-up, and language-switch acceptance
  checks remain unverified in its README. POC-05 has not been live-tested with
  Gemini in this sandbox.

The POC-05 test command could not start here because `python` is not recognized
in the shell. Do not treat the authored tests or offline demonstration as
executed results until Windows CMD output confirms them.

## Limitations

- State is process-local and disappears on exit; there is no authentication,
  persistence, synchronization, or PostgreSQL adapter yet.
- The in-memory store returns object references and is intended for this single
  process POC; a durable adapter must add transactional concurrency controls.
- Voice is only a text transcript and visual is only a metadata event.
- LLM quality and evaluation can vary; Telugu and mixed-language content needs
  review. Provider failures do not create failed chat turns; an answer already
  evaluated by POC-04 remains in progress history if response generation fails.
