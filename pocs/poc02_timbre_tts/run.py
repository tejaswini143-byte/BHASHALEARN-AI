"""CLI for English/Telugu GNANI Timbre v2.5 synthesis."""
import argparse
from pathlib import Path

from dotenv import load_dotenv
from timbre_tts import TimbreConfig, TimbreTTSAdapter, TTSError, write_audio


def main() -> int:
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="GNANI Timbre v2.5 TTS POC")
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--language", choices=["en-IN", "te-IN", "auto"], default="en-IN")
    parser.add_argument("--voice", help="Optional voice override")
    parser.add_argument("--output", default="output.wav", help="Destination WAV filename")
    args = parser.parse_args()
    try:
        adapter = TimbreTTSAdapter(TimbreConfig.from_env())
        audio = adapter.synthesize(args.text, language=args.language, voice=args.voice)
        path = write_audio(audio, args.output)
        print(f"POC-02 success: saved {path} ({len(audio)} bytes)")
        return 0
    except TTSError as exc:
        print(f"POC-02 failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
