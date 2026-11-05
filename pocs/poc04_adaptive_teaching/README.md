# POC-04 — Adaptive Teaching Logic

An in-memory adaptive tutoring layer for English, Telugu, and Telugu-English
mixed lessons. It tracks a learner's recent evidence, evaluates answers,
selects a teaching strategy, and adjusts difficulty only after enough evidence.

## Architecture

```text
CLI -> AdaptiveSession -> POC-03 Tutor -> POC-03 LLMClient -> Gemini-compatible API
                 |              ^
                 v              |
     AdaptiveTeachingEngine -> evaluator
                 |
                 +-> StudentState + policy (no provider dependency)
```

`models.py`, `adaptation.py`, and deterministic objective checking do not depend
on Gemini or HTTP. `StructuredLLMEvaluator` accepts an injected object that
implements POC-03's `complete(messages)` interface. `AdaptiveSession` reuses
POC-03's bounded conversation, language switch, and teaching prompt. Each
`StudentState` belongs to one session and is held in memory; its typed fields
are suitable for a later persistence adapter, but this POC does not persist
them.

## Learning state

`StudentState` contains student and session IDs, topic, preferred language,
difficulty, a bounded list of typed answer records, total outcome counts,
attempts, hint usage, recent scored performance, and mastery evidence. It also
stores the bounded history limit and evidence index of the most recent
difficulty change so later persistence can restore policy behavior. Separate
state instances keep students isolated.

## Answer evaluation

- Objective questions use normalized exact matching against accepted and
  explicitly partial answers. Empty or obvious uncertainty answers are
  `ambiguous`; they do not affect mastery.
- Open-ended answers ask the injected LLM for JSON with an outcome, feedback,
  explanation, and optional confidence. The parser rejects invalid JSON,
  unknown fields or outcomes, missing text, and out-of-range confidence.
- Provider errors and malformed evaluations produce a safe retry response and
  do not enter the learner's evidence history. LLM judgments are estimates,
  not guaranteed truth; use human review for consequential assessment.

## Mastery and adaptation

Each scored response maps to 1.0 for correct, 0.5 for partially correct, and
0.0 for incorrect. Ambiguous responses are omitted. Mastery is the smoothed
fraction:

```text
mastery = (2 + sum(scored response points)) / (4 + scored response count)
```

The two virtual successes and two virtual misses are a Beta(2,2) prior, so a
new learner starts at 0.50 and a single answer cannot produce an extreme score.
The estimate is clamped by construction to 0.0–1.0.

Default policy thresholds are configurable through `AdaptiveConfig`:

- Three recent scored answers with at least 80% on each promote one difficulty
  level; advanced is the cap.
- Three recent scored answers averaging below 40% demote one level; beginner
  is the floor. A three-evidence cooldown prevents repeated transitions.
- The first incorrect answer triggers a hint; two consecutive mistakes select
  a simpler example; three select prerequisite review.
- Mastery of 80% or more selects challenging practice. Partial answers receive
  an alternative explanation; ambiguous answers receive a clarification.
- The transition thresholds use evaluated evidence, not provider failures or
  ambiguous answers.

Strategies include step-by-step teaching, hint, simpler example, alternative
explanation, prerequisite review, practice, challenging practice, and
constructive feedback. The selected strategy is converted to a directive and
sent through the existing POC-03 Tutor using the selected language.

## Windows CMD

From Windows CMD, create a local environment and install POC-03's shared
runtime and test dependencies:

```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
python --version
python -m venv .venv
call .venv\Scripts\activate
python -m pip install -r pocs\poc03_bilingual_llm\requirements.txt
python -m pytest -q pocs\poc04_adaptive_teaching\tests
python -m pocs.poc04_adaptive_teaching.simulate
python pocs\poc04_adaptive_teaching\run.py
```

The CLI reads the existing local `pocs\poc03_bilingual_llm\.env`; it does not
create or copy credentials. Select a language and topic, answer the practice
question, then use `/language english`, `/language telugu`, `/language mixed`,
`/reset`, or `/quit`. A key must never be committed.

## Deterministic profile simulation

`simulate.py` uses scripted outcomes and makes no API calls. Expected decisions:

| Profile | Evidence | Mastery | Difficulty | Last strategy |
| --- | --- | ---: | --- | --- |
| Student A — struggling | 3 incorrect | 29% | intermediate → beginner | prerequisite review |
| Student B — improving | partial, then 3 correct | 69% | beginner → intermediate | practice |
| Student C — strong | 6 correct | 80% | intermediate → advanced | challenging practice |

## Verification results

- Automated tests: **not run in this Codex workspace**. The suite defines 28
  deterministic test cases. `python` is not on the shell `PATH`; direct access
  to the documented Python 3.12 installation and the base Python used by the
  existing POC-02 virtual environment returned `Access is denied`. The test
  command failed with PowerShell's `The term 'python' is not recognized`
  message. The test cases are present, but no passing count is
  claimed. Run the CMD command above and replace this note with the actual
  result.
- Live Gemini testing: **blocked for POC-04 in this Codex workspace**. A
  credential-safe connectivity probe using the configured model failed with
  the exact client error `Unable to connect to the remote server`. This does
  not contradict the POC-03 README's successful basic Gemini test in normal
  Windows CMD. POC-03's dedicated Telugu, mixed-language, follow-up/context,
  and language-switch acceptance checks remain pending there. POC-04's
  adaptive evaluation and bilingual response quality have not been live-tested.
- The Codex workspace currently denies writing new refs under `.git`; branch
  creation, commit, and push must be completed from normal Windows CMD if that
  restriction remains.

## Limitations

- State is volatile and process-local; no database, cross-device sync, or
  learner authentication is implemented.
- The LLM evaluator can misjudge correct answers, especially multilingual,
  spelling-variant, or open-ended responses. Review before using scores for
  grades or high-impact decisions.
- Objective matching is exact after Unicode normalization; it does not handle
  algebraic equivalence or semantic variants unless they are explicitly listed.
- Difficulty and strategy rules are transparent heuristics, not a validated
  learning-science model. Telugu and mixed-language output needs human review.
- The CLI uses a broad reference rubric and asks for the answer/evaluation and
  teacher response as separate provider calls, adding latency and token cost.

