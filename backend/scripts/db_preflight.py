"""Read-only database and Alembic preflight for local INT-01 development.

Run from the repository root with ``python -m backend.scripts.db_preflight``.
The report deliberately omits database usernames, passwords, and URLs.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db import models  # noqa: F401 - register mapped tables


def _safe_target(database_url: str) -> str:
    """Return host/port/database only; never include URL user info or query."""
    try:
        parsed = urlsplit(database_url)
        host = parsed.hostname or "unknown-host"
        port = parsed.port or "default-port"
        database = Path(parsed.path).name or "unknown-database"
        return f"{host}:{port}/{database}"
    except (TypeError, ValueError):
        return "unparseable database target (URL redacted)"


def run_preflight(database_url: str | None = None) -> tuple[bool, list[str]]:
    """Check connectivity, migration head, and ORM tables without changing DB."""
    report: list[str] = []
    engine = None
    try:
        database_url = database_url or Settings().database_url
        report.append(f"Target: {_safe_target(database_url)}")
        engine = create_engine(database_url, pool_pre_ping=True, pool_timeout=5)
        with engine.connect() as connection:
            report.append("Connection and credential authentication: PASS")
            config = Config(str(Path("backend/alembic.ini")))
            scripts = ScriptDirectory.from_config(config)
            current = MigrationContext.configure(connection).get_current_revision()
            heads = scripts.get_heads()
            if len(heads) != 1:
                report.append(f"Alembic heads: FAIL (expected one head, found {len(heads)})")
                return False, report
            expected = heads[0]
            if current != expected:
                shown_current = current or "none"
                report.append(f"Migration state: FAIL (database={shown_current}, expected={expected})")
                report.append("Apply migrations only after confirming this is a local development database:")
                report.append("  python -m alembic -c backend/alembic.ini upgrade head")
                return False, report
            report.append(f"Migration state: PASS ({current}; at repository head)")

            inspector = inspect(connection)
            existing = set(inspector.get_table_names())
            required = set(Base.metadata.tables)
            missing = sorted(required - existing)
            if missing:
                report.append("Schema tables: FAIL (missing: " + ", ".join(missing) + ")")
                return False, report
            report.append(f"Schema tables: PASS ({len(required)} application tables present)")
            return True, report
    except SQLAlchemyError as exc:
        # Do not emit the provider exception text: it can contain connection details.
        report.append(f"Connection and credential authentication: FAIL ({type(exc).__name__})")
        report.append(
            "Check BHASHALEARN_DATABASE_URL in the repository root .env; "
            "confirm the local PostgreSQL service, database name, port, and credentials. "
            "Do not paste credentials into logs or support messages."
        )
        return False, report
    except Exception as exc:
        # Settings/URL validation errors can include user supplied values.
        report.append(f"Configuration or preflight: FAIL ({type(exc).__name__})")
        report.append(
            "Check BHASHALEARN_DATABASE_URL in the repository root .env and "
            "confirm it is a valid SQLAlchemy PostgreSQL URL. Credentials are redacted."
        )
        return False, report
    finally:
        if engine is not None:
            engine.dispose()


def main() -> int:
    ok, report = run_preflight()
    print("INT-01 database preflight (read-only)")
    for line in report:
        print(line)
    print("Overall: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
