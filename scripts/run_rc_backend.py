"""Start the local RC API with parent-project provider config, without file edits."""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT), *(entry for entry in sys.path if Path(entry or ".").resolve() != ROOT)]

from pocs.poc06_bilingual_voice.config import load_provider_environment  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BHASHALEARN integration RC backend locally.")
    parser.add_argument("--host", default=os.environ.get("BHASHALEARN_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("BHASHALEARN_PORT", "8027")))
    args = parser.parse_args()

    load_provider_environment(ROOT)
    if not os.environ.get("BHASHALEARN_DATABASE_URL", "").strip():
        raise SystemExit("Set BHASHALEARN_DATABASE_URL to the approved local database before starting the backend.")
    # Keep request-scoped audio/PDF temp files inside the disposable RC area;
    # some managed Windows package temp folders are readable but not writable.
    runtime_temp = ROOT / ".test-tmp" / "rc-process-temp"
    runtime_temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(runtime_temp)
    os.environ["TMP"] = str(runtime_temp)
    if not os.environ.get("BHASHALEARN_JWT_SECRET_KEY", "").strip():
        os.environ["BHASHALEARN_JWT_SECRET_KEY"] = secrets.token_urlsafe(48)
    # One in-process durable worker for the local RC. Other app instances and
    # tests stay disabled unless explicitly configured.
    os.environ.setdefault("BHASHALEARN_LOCAL_SCHEDULER_ENABLED", "true")

    import uvicorn

    uvicorn.run("backend.app.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
