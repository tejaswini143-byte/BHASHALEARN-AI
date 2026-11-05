"""Interactive full voice pipeline CLI; microphone is optional, PCM WAV is the fallback."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pocs.poc01_prisma_stt.prisma_stt import PrismaConfig
from pocs.poc02_timbre_tts.timbre_tts import TimbreConfig, TimbreTTSAdapter
from pocs.poc03_bilingual_llm.config import ConfigurationError, LLMConfig
from pocs.poc03_bilingual_llm.llm_client import LLMClient
from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import ObjectiveQuestion, StructuredLLMEvaluator
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc05_shared_session_context.manager import SessionManager
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime

from pocs.poc06_bilingual_voice.audio import AudioCapture, AudioInputError, MicrophoneRecorder, WavAudioInput, play_wav
from pocs.poc06_bilingual_voice.config import VoiceConfigError, VoicePipelineConfig, load_provider_environment
from pocs.poc06_bilingual_voice.stt_adapter import PrismaTranscriptionAdapter
from pocs.poc06_bilingual_voice.tts_adapter import TimbreSpeechAdapter
from pocs.poc06_bilingual_voice.voice_pipeline import VoicePipeline, VoicePipelineResult


def build_pipeline(manager: SessionManager, session_id: str, repo_root: Path = REPO_ROOT) -> VoicePipeline:
    load_provider_environment(repo_root)
    try:
        llm_config = LLMConfig.from_env()
        prisma_config = PrismaConfig.from_env()
        timbre_config = TimbreConfig.from_env()
        voice_config = VoicePipelineConfig.from_env(repo_root)
    except (ConfigurationError, VoiceConfigError, RuntimeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc
    llm = LLMClient(llm_config)
    tutor = Tutor(llm, language=manager.get_session(session_id).language.value)
    runtime = SharedSessionRuntime(manager, session_id, tutor, StructuredLLMEvaluator(llm))
    stt = PrismaTranscriptionAdapter.from_config(prisma_config)
    tts = TimbreSpeechAdapter.from_config(TimbreTTSAdapter(timbre_config), voice_config.output_dir)
    return VoicePipeline(stt, runtime, tts, manager)


def _question_for_topic(topic: str) -> tuple[str, str, ObjectiveQuestion | None]:
    if topic.casefold() in {"fraction", "fractions", "equivalent fractions"}:
        return (
            "Which fraction is equivalent to 1/2: 2/4 or 3/4?",
            "An equivalent fraction with the same value as one half, such as 2/4.",
            ObjectiveQuestion(("2/4", "4/8", "1/2"), ("equivalent fraction",)),
        )
    return f"Explain {topic} in your own words and give one example.", f"An accurate explanation of {topic} with an example.", None


def _show_result(result: VoicePipelineResult, save_only: bool) -> None:
    if result.transcript is not None:
        print(f"Transcript: {result.transcript.text or '[no speech recognized]'}")
    if result.tutor_response:
        print(f"Teacher: {result.tutor_response}")
    if result.topic is not None:
        print(
            f"Context: topic={result.topic}; language={result.language.value}; "
            f"difficulty={result.difficulty.value}; mastery={result.mastery_score:.0%}; "
            f"strategy={result.adaptive_strategy or 'none'}"
        )
    if result.audio is not None:
        print(
            f"Audio: {result.audio.path} ({result.audio.size_bytes} bytes, "
            f"{result.audio.duration_seconds:.2f}s, {result.audio.sample_rate} Hz, voice={result.audio.voice})"
        )
        if not save_only:
            try:
                play_wav(result.audio.path)
            except AudioInputError as exc:
                print(f"Playback note: {exc}")
    for stage, seconds in result.latency_seconds.items():
        print(f"Latency {stage}: {seconds:.3f}s")
    for error in result.errors:
        retry = " (retryable)" if error.retryable else ""
        print(f"{error.stage} error [{error.code}]{retry}: {error.message}")


def main() -> int:
    parser = argparse.ArgumentParser(description="BHASHALEARN POC-06 bilingual voice tutor")
    parser.add_argument("--save-only", action="store_true", help="Save the WAV without automatic playback")
    args = parser.parse_args()

    student_id = input("Student ID [learner]: ").strip() or "learner"
    try:
        language = Language(input("Language (english/telugu/mixed) [mixed]: ").strip().lower() or "mixed")
    except ValueError:
        print("Choose english, telugu, or mixed.")
        return 1
    topic = input("Topic [fractions]: ").strip() or "fractions"
    manager = SessionManager()
    context = manager.create_session(
        student_id,
        topic,
        language,
        lesson_objective=f"Understand {topic} and explain an example.",
    )
    try:
        load_provider_environment(REPO_ROOT)
        voice_config = VoicePipelineConfig.from_env(REPO_ROOT)
        pipeline = build_pipeline(manager, context.session_id)
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 1
    runtime = pipeline.runtime
    question, reference, objective = _question_for_topic(topic)
    recorder = MicrophoneRecorder(voice_config.sample_rate, voice_config.channels, voice_config.max_recording_seconds)

    try:
        intro = runtime.start_lesson(topic, context.lesson_objective)
        print(f"Session {context.session_id} | {language.value} | {topic}")
        print(f"Teacher: {intro.response}")
        print(f"Practice answer prompt: {question}")
    except Exception as exc:
        print(f"Lesson request failed: {exc}")
        return 1

    def process_capture(capture: AudioCapture, as_answer: bool = False) -> None:
        try:
            result = pipeline.process_audio(
                context.session_id,
                capture.path,
                question=question if as_answer else None,
                reference_answer=reference,
                objective=objective if as_answer else None,
            )
            _show_result(result, args.save_only)
        finally:
            capture.cleanup()

    print("Commands: /record, /file <wav>, /answer <wav>, /topic <topic>, /language <mode>, /context, /reset, /end")
    while True:
        try:
            line = input("POC-06: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            manager.end_session(context.session_id)
            return 0
        if not line:
            continue
        command, _, argument = line.partition(" ")
        argument = argument.strip().strip('"')
        try:
            if command.lower() in {"/end", "/quit"}:
                manager.end_session(context.session_id)
                print("Session ended.")
                return 0
            if command.lower() == "/record":
                capture = recorder.record(VoicePipelineConfig.from_env(REPO_ROOT).recording_seconds)
                process_capture(capture)
            elif command.lower() == "/file":
                process_capture(WavAudioInput.from_file(argument))
            elif command.lower() == "/answer":
                process_capture(WavAudioInput.from_file(argument), as_answer=True)
            elif command.lower() == "/language":
                runtime.switch_language(argument)
                print(f"Language changed to {manager.get_session(context.session_id).language.value}.")
            elif command.lower() == "/topic":
                topic = argument
                question, reference, objective = _question_for_topic(topic)
                response = runtime.start_lesson(topic, f"Understand {topic} and explain an example.")
                print(f"Teacher: {response.response}\nPractice answer prompt: {question}")
            elif command.lower() == "/context":
                current = manager.get_teaching_context(context.session_id)
                print(
                    f"topic={current.topic}; language={current.language.value}; difficulty={current.difficulty.value}; "
                    f"mastery={current.mastery_score:.0%}; hint_usage={current.hint_usage}; "
                    f"strategy={current.adaptive_strategy or 'none'}; turns={len(current.recent_turns)}"
                )
            elif command.lower() == "/reset":
                runtime.reset()
                runtime.start_lesson(topic, f"Understand {topic} and explain an example.")
                print("Session learning state and conversation history reset; language/topic retained.")
            elif command.lower() == "/start":
                response = runtime.start_lesson()
                print(f"Teacher: {response.response}")
            else:
                print("Use a supported command. Microphone and WAV input are available through /record and /file.")
        except (AudioInputError, ValueError, RuntimeError) as exc:
            print(f"Request failed: {exc}")


if __name__ == "__main__":
    raise SystemExit(main())

