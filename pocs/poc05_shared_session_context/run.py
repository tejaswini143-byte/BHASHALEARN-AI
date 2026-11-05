"""Interactive shared-context demo for chat, adaptive answers, voice, and visual events."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from pocs.poc03_bilingual_llm.config import ConfigurationError, LLMConfig
from pocs.poc03_bilingual_llm.llm_client import LLMClient
from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import ObjectiveQuestion, StructuredLLMEvaluator
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc05_shared_session_context.context import Modality
from pocs.poc05_shared_session_context.manager import SessionManager
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime


def main() -> int:
    load_dotenv(REPO_ROOT / "pocs" / "poc03_bilingual_llm" / ".env")
    try:
        client = LLMClient(LLMConfig.from_env())
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 1

    student_id = input("Student ID [learner]: ").strip() or "learner"
    try:
        language = Language(input("Language (english/telugu/mixed) [mixed]: ").strip().lower() or "mixed")
    except ValueError:
        print("Choose english, telugu, or mixed.")
        return 1
    topic = input("Topic [fractions]: ").strip() or "fractions"

    manager = SessionManager()
    context = manager.create_session(
        student_id=student_id,
        topic=topic,
        language=language,
        lesson_objective=f"Understand {topic} and explain one equivalent example.",
    )
    tutor = Tutor(client, language=language.value, level=context.difficulty.value)
    runtime = SharedSessionRuntime(manager, context.session_id, tutor, StructuredLLMEvaluator(client))
    if topic.casefold() in {"fraction", "fractions", "equivalent fractions"}:
        question = "Which fraction is equivalent to 1/2: 2/4 or 3/4?"
        objective = ObjectiveQuestion(("2/4", "4/8", "1/2"), ("equivalent fraction",))
        reference = "An equivalent fraction with the same value as one half, such as 2/4."
    else:
        question = f"Explain {topic} in your own words and give one example."
        objective = None
        reference = f"An accurate explanation of {topic} with a relevant example."

    try:
        intro = runtime.start_lesson()
    except Exception as exc:
        print(f"Lesson request failed: {exc}")
        return 1
    print(f"\nSession {context.session_id} | {topic} | {language.value}")
    print("Teacher:", intro.response)
    print(f"Practice: {question}")
    print("Commands: /answer <answer>, /voice <simulated transcript>, /language <language>, /visual <event>, /context, /reset, /end")

    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        command, _, payload = line.partition(" ")
        payload = payload.strip()
        try:
            if command.lower() == "/answer":
                interaction = runtime.adaptive_answer(question, payload, reference, objective)
                decision = interaction.decision
                print(f"Assessment: {decision.evaluation.outcome.value}; hint strategy: {decision.strategy.value}")
                print(f"Mastery: {decision.mastery_score:.0%}; difficulty: {decision.difficulty_after.value}")
                print("Teacher:", interaction.response)
            elif command.lower() == "/voice":
                interaction = runtime.voice_transcript(payload)
                print("Teacher:", interaction.response)
            elif command.lower() == "/language":
                runtime.switch_language(payload)
                print(f"Language is now {manager.get_session(context.session_id).language.value}.")
            elif command.lower() == "/visual":
                runtime.record_visual_event(payload, {"kind": "future_visual_lesson_event"})
                print("Visual lesson context recorded without image processing.")
            elif command.lower() == "/context":
                current = manager.get_teaching_context(context.session_id)
                print(
                    f"topic={current.topic}; language={current.language.value}; difficulty={current.difficulty.value}; "
                    f"mastery={current.mastery_score:.0%}; hints={current.hint_usage}; "
                    f"strategy={current.adaptive_strategy or 'none'}; events={len(current.recent_turns)}"
                )
            elif command.lower() == "/reset":
                runtime.reset()
                intro = runtime.start_lesson(topic, f"Understand {topic} and explain one example.")
                print("Session context reset; student, topic, language, and session ID retained.")
                print("Teacher:", intro.response)
            elif command.lower() == "/end":
                runtime.end()
                print("Session ended.")
                return 0
            elif command.lower() == "/quit":
                runtime.end()
                print("Session ended.")
                return 0
            else:
                interaction = runtime.chat(line)
                print("Teacher:", interaction.response)
        except Exception as exc:
            print(f"Request failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
