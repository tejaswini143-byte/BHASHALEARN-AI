"""Database engine and session management."""
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url.strip()
    normalized_url = database_url.casefold()
    if (
        not database_url
        or "your_db_user" in normalized_url
        or "your_db_password" in normalized_url
        or "your_db_name" in normalized_url
        or "replace-" in normalized_url
        or "replace_" in normalized_url
        or "<" in database_url
    ):
        raise RuntimeError("Database is not configured; set BHASHALEARN_DATABASE_URL.")
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db():
    """Yield one session per request and close it afterward."""
    with get_session_factory()() as session:
        yield session
