"""Interactive CLI for the POC-03 bilingual teacher."""
from pathlib import Path

from dotenv import load_dotenv

try:
    from .config import ConfigurationError, LLMConfig
    from .llm_client import LLMClient, LLMProviderError
    from .tutor import Tutor
except ImportError:
    from config import ConfigurationError, LLMConfig
    from llm_client import LLMClient, LLMProviderError
    from tutor import Tutor


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    try:
        tutor = Tutor(LLMClient(LLMConfig.from_env()))
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}")
        return 1
    print("BhashaLearn POC-03 — /language english|telugu|mixed, /level beginner|intermediate|advanced, /quit")
    while True:
        try:
            line = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line.lower() in {"/quit", "/exit"}:
            return 0
        if line.startswith("/language "):
            try:
                tutor.set_language(line.split(maxsplit=1)[1].lower())
                print(f"Teaching language: {tutor.language}")
            except (ValueError, IndexError) as exc:
                print(f"Command error: {exc}")
            continue
        if line.startswith("/level "):
            try:
                tutor.set_level(line.split(maxsplit=1)[1].lower())
                print(f"Student level: {tutor.level}")
            except (ValueError, IndexError) as exc:
                print(f"Command error: {exc}")
            continue
        try:
            print(f"Teacher: {tutor.ask(line)}")
        except (ValueError, LLMProviderError) as exc:
            print(f"Teaching request failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())
