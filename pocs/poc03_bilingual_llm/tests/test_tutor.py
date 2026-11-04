import pytest

try:
    from pocs.poc03_bilingual_llm.config import ConfigurationError, LLMConfig
    from pocs.poc03_bilingual_llm.llm_client import LLMClient, LLMProviderError
    from pocs.poc03_bilingual_llm.prompts import build_system_prompt
    from pocs.poc03_bilingual_llm.tutor import Tutor
except ModuleNotFoundError:
    from config import ConfigurationError, LLMConfig
    from llm_client import LLMClient, LLMProviderError
    from prompts import build_system_prompt
    from tutor import Tutor


class FakeProvider:
    def __init__(self, answers=None, error=None):
        self.answers = answers or ["Let us reason it through step by step."]
        self.error = error
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.answers[min(len(self.calls) - 1, len(self.answers) - 1)]


@pytest.mark.parametrize("language,expected", [
    ("english", "English"),
    ("telugu", "Telugu, written naturally in Telugu script"),
    ("mixed", "natural Telugu-English code-mixing"),
])
def test_fraction_teaching_languages(language, expected):
    provider = FakeProvider()
    tutor = Tutor(provider, language=language)
    tutor.ask("Explain fractions")
    assert expected in provider.calls[0][0]["content"]


def test_beginner_and_advanced_prompts_change_depth():
    beginner = build_system_prompt("english", "beginner")
    advanced = build_system_prompt("english", "advanced")
    assert "beginner learner" in beginner
    assert "advanced learner" in advanced


def test_switch_language_keeps_conversation_history():
    provider = FakeProvider(answers=["An explanation.", "వివరణ."])
    tutor = Tutor(provider)
    tutor.ask("Explain a fraction")
    tutor.set_language("telugu")
    tutor.ask("ఇంకొంచెం వివరించండి")
    second_call = provider.calls[1]
    assert second_call[0]["content"].startswith("You are BhashaLearn")
    assert second_call[0]["content"].find("Telugu") >= 0
    assert second_call[1:3] == [
        {"role": "user", "content": "Explain a fraction"},
        {"role": "assistant", "content": "An explanation."},
    ]


def test_follow_up_uses_prior_turn_context():
    provider = FakeProvider(answers=["A numerator is the top number.", "It is the numerator."])
    tutor = Tutor(provider)
    tutor.ask("What is the top number called?")
    tutor.ask("What did you call it?")
    assert provider.calls[1][1]["content"] == "What is the top number called?"
    assert provider.calls[1][2]["content"] == "A numerator is the top number."
    assert provider.calls[1][-1]["content"] == "What did you call it?"


def test_guided_practice_and_kind_correction_prompt():
    prompt = build_system_prompt("english", "beginner").lower()
    assert "hint or a question before revealing" in prompt
    assert "identify the misconception" in prompt


def test_history_is_bounded():
    provider = FakeProvider(answers=[f"answer {n}" for n in range(8)])
    tutor = Tutor(provider, max_turns=2)
    for n in range(4):
        tutor.ask(f"question {n}")
    assert len(tutor.history) == 4
    assert tutor.history[0]["content"] == "question 2"


def test_missing_api_credentials(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(ConfigurationError, match="LLM_API_KEY"):
        LLMConfig.from_env()


def test_provider_http_error_is_safe():
    import requests

    class ErrorSession:
        def post(self, *args, **kwargs):
            response = requests.Response()
            response.status_code = 503
            raise requests.HTTPError("error", response=response)

    with pytest.raises(LLMProviderError, match="HTTP 503"):
        LLMClient(LLMConfig("test-secret"), ErrorSession()).complete([])


def test_provider_failure_does_not_commit_failed_turn():
    provider = FakeProvider(error=LLMProviderError("offline"))
    tutor = Tutor(provider)
    with pytest.raises(LLMProviderError):
        tutor.ask("Explain fractions")
    assert tutor.history == []
