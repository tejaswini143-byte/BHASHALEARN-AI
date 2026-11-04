"""POC-02 CLI; live synthesis intentionally gated until API schema verification."""
import argparse
from pathlib import Path

from dotenv import load_dotenv
from timbre_tts import TimbreConfig, TimbreTTSAdapter, TTSError


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    parser = argparse.ArgumentParser(description="GNANI Timbre v2.5 TTS POC")
    parser.add_argument("text", help="Text to synthesize")
    args = parser.parse_args()
    try:
        TimbreTTSAdapter(TimbreConfig.from_env()).synthesize(args.text)
    except TTSError as exc:
        print(f"POC-02 pending: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
