"""Run: python run.py path/to/recording.wav"""
import argparse
from dotenv import load_dotenv

from prisma_stt import PrismaConfig, PrismaSTTAdapter, STTError


def main() -> int:
    parser = argparse.ArgumentParser(description="GNANI Prisma POC-01")
    parser.add_argument("audio", help="Path to a short PCM WAV recording")
    args = parser.parse_args()
    load_dotenv()
    try:
        transcript = PrismaSTTAdapter(PrismaConfig.from_env()).transcribe(args.audio)
        print("Transcript:", transcript.text)
        print("Language:", transcript.language or "not returned")
        return 0
    except STTError as exc:
        print("POC-01 failed:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
