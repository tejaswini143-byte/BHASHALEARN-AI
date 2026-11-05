"""Storage contract and thread-safe in-memory POC implementation."""
from __future__ import annotations

from threading import RLock
from typing import Protocol

from .context import SessionContext


class SessionAlreadyExistsError(ValueError):
    pass


class SessionStore(Protocol):
    """Persistence interface a PostgreSQL-backed adapter can implement later."""

    def create(self, context: SessionContext) -> None: ...
    def get(self, session_id: str) -> SessionContext | None: ...
    def save(self, context: SessionContext) -> None: ...
    def list_all(self) -> list[SessionContext]: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}
        self._lock = RLock()

    def create(self, context: SessionContext) -> None:
        with self._lock:
            if context.session_id in self._sessions:
                raise SessionAlreadyExistsError("session ID already exists")
            self._sessions[context.session_id] = context

    def get(self, session_id: str) -> SessionContext | None:
        with self._lock:
            return self._sessions.get(session_id)

    def save(self, context: SessionContext) -> None:
        with self._lock:
            if context.session_id not in self._sessions:
                raise KeyError("session does not exist")
            self._sessions[context.session_id] = context

    def list_all(self) -> list[SessionContext]:
        with self._lock:
            return list(self._sessions.values())
