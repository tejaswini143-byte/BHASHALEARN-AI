"""Offline, deterministic end-to-end walkthrough using the real POC adapters and mocked providers."""
from __future__ import annotations

import io
import tempfile
import wave
from pathlib import Path

from pocs.poc01_prisma_stt.prisma_stt import Transcript
from pocs.poc02_timbre_tts.timbre_tts import TimbreConfig
from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import DeterministicEvaluator, ObjectiveQuestion
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc05_shared_session_context.manager import SessionManager
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime

from .stt_adapter import PrismaTranscriptionAdapter
from .tts_adapter import TimbreSpeechAdapter
from .voice_pipeline import VoicePipeline


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\x00\x00" * 160)
    return buffer.getvalue()


def _speech_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes(b"\x00\x00" * 480)
    return buffer.getvalue()


class ScriptPrisma:
    def __init__(self, utterances: list[str]):
        self.utterances = iter(utterances)

    def transcribe(self, audio_path: str | Path) -> Transcript:
        text = next(self.utterances)
        return Transcript(text, "te-en", {"transcript": text, "detected_language_code": "te-en", "mock": True})


class DemoGemini:
    def __init__(self):
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        prompt = messages[-1]["content"].lower()
        if "adaptation strategy: hint" in prompt:
            return "Hint: simplify both the numerator and denominator by the same number."
        if "strategy: step_by_step" in prompt:
            return "Correct. 2/4 simplifies to 1/2 because both parts divide by 2."
        if "another example" in prompt:
            return "For example, 3/6 also equals 1/2."
        return "Fractions represent equal parts of a whole. PRACTICE QUESTION: Which fraction equals one half?"


class DemoTimbre:
    def synthesize(self, text, language="en-IN", voice=None):
        return _speech_bytes()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="bhashalearn-poc06-") as temp_dir:
        temp_root = Path(temp_dir)
        wav_path = temp_root / "demo-input.wav"
        wav_path.write_bytes(_wav_bytes())
        manager = SessionManager()
        context = manager.create_session(
            "student-demo",
            "fractions",
            Language.MIXED,
            lesson_objective="Understand equivalent fractions.",
        )
        provider = DemoGemini()
        tutor = Tutor(provider, language=Language.MIXED.value)
        runtime = SharedSessionRuntime(manager, context.session_id, tutor, DeterministicEvaluator())
        stt = PrismaTranscriptionAdapter(ScriptPrisma([
            "3/4",
            "2/4",
            "Can you give another example?",
        ]))
        tts_config = TimbreConfig(api_key="mock-only", voice="Suhana")
        tts = TimbreSpeechAdapter(DemoTimbre(), tts_config, temp_root / "output")
        pipeline = VoicePipeline(stt, runtime, tts, manager)

        intro = runtime.start_lesson(objective="Understand equivalent fractions.")
        print(f"Session created: {context.student_id} | mixed | fractions")
        print(f"Lesson: {intro.response}")
        question = "Which fraction is equivalent to 1/2?"
        objective = ObjectiveQuestion(("2/4", "4/8", "1/2"))

        wrong = pipeline.process_audio(context.session_id, wav_path, question=question, objective=objective)
        print(f"STT: {wrong.transcript.text}; evaluation={wrong.errors or wrong.adaptive_strategy}")
        print(f"Hint: {wrong.tutor_response}")
        print(f"Hint audio: {wrong.audio.path if wrong.audio else 'not generated'}")

        corrected = pipeline.process_audio(context.session_id, wav_path, question=question, objective=objective)
        print(f"STT: {corrected.transcript.text}; mastery={corrected.mastery_score:.0%}; difficulty={corrected.difficulty.value}")
        print(f"Corrected audio: {corrected.audio.path if corrected.audio else 'not generated'}")

        follow_up = pipeline.process_audio(context.session_id, wav_path)
        current = manager.get_teaching_context(context.session_id)
        assert any("Which fraction is equivalent" in message["content"] for message in provider.calls[-1])
        assert current.language is Language.MIXED and current.topic == "fractions"
        assert current.mastery_score == 0.5 and current.hint_usage == 1
        print(f"Voice follow-up: {follow_up.transcript.text} -> {follow_up.tutor_response}")
        print(
            f"Context preserved: topic={current.topic}; language={current.language.value}; "
            f"mastery={current.mastery_score:.0%}; hints={current.hint_usage}; "
            f"difficulty={current.difficulty.value}"
        )
        print(f"Latency (follow-up): {follow_up.latency_seconds}")
        manager.end_session(context.session_id)
        print("Session ended.")


if __name__ == "__main__":
    main()

