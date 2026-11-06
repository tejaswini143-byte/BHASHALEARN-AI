"""Fail closed unless the active DB and private storage are ADV-01 E2E-only."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DATABASE = "bhashalearn_e2e_test"
EXPECTED_USER = "bhashalearn_e2e"
EXPECTED_STORAGE = (REPO_ROOT / "test-data" / "private-documents").resolve()
REAL_STORAGE = (REPO_ROOT / "backend" / "storage" / "documents").resolve()


def main() -> None:
    database_url = os.environ.get("BHASHALEARN_DATABASE_URL")
    if not database_url:
        raise SystemExit("E2E isolation check failed: BHASHALEARN_DATABASE_URL is not explicitly set.")

    parsed = urlparse(database_url)
    database_name = unquote(parsed.path.lstrip("/"))
    username = unquote(parsed.username or "")
    if database_name != EXPECTED_DATABASE or username != EXPECTED_USER:
        raise SystemExit("E2E isolation check failed: configured PostgreSQL target is not the dedicated E2E database and role.")

    configured_storage = os.environ.get("BHASHALEARN_DOCUMENT_STORAGE_DIR")
    if not configured_storage:
        raise SystemExit("E2E isolation check failed: BHASHALEARN_DOCUMENT_STORAGE_DIR is not explicitly set.")
    storage_path = Path(configured_storage).resolve()
    expected_root = (REPO_ROOT / "test-data").resolve()
    if storage_path != EXPECTED_STORAGE or expected_root not in storage_path.parents:
        raise SystemExit("E2E isolation check failed: document storage is not the dedicated test-data directory.")
    if storage_path == REAL_STORAGE or storage_path in REAL_STORAGE.parents or REAL_STORAGE in storage_path.parents:
        raise SystemExit("E2E isolation check failed: test document storage overlaps real document storage.")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            active_database, active_user = connection.execute(
                text("SELECT current_database(), current_user")
            ).one()
    finally:
        engine.dispose()

    if active_database != EXPECTED_DATABASE or active_user != EXPECTED_USER:
        raise SystemExit("E2E isolation check failed: live PostgreSQL identity did not match the expected database and role.")

    print("E2E database verified: current_database=bhashalearn_e2e_test current_user=bhashalearn_e2e")
    print(f"E2E document storage verified: {storage_path}")


if __name__ == "__main__":
    main()
