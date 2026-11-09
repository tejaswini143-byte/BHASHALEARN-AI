"""Run the persistent INT17 database worker: python -m backend.scripts.assistant_worker"""
import argparse
import logging
import time

from backend.app.db.session import get_session_factory
from backend.app.services.assistant_worker import run_due_jobs
from backend.app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Process persisted assistant reminders (safe mock mode).")
    parser.add_argument("--once", action="store_true", help="Process one due-job batch and exit")
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=25)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    factory = get_session_factory()
    settings = get_settings()
    allow_live = settings.app_env == "production" and settings.assistant_live_operations_enabled
    while True:
        try:
            with factory() as db:
                count = run_due_jobs(db, limit=args.batch_size, allow_live_operations=allow_live)
            if count:
                logging.info("Recorded %s mock reminder outcomes", count)
        except Exception:
            logging.exception("Assistant worker batch failed; jobs remain persisted for retry")
        if args.once:
            break
        time.sleep(max(1, args.poll_seconds))


if __name__ == "__main__":
    main()
