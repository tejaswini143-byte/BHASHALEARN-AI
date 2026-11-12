from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_local_reminder_scheduler_is_opt_in_and_stops(monkeypatch):
    workers = []

    class Worker:
        def __init__(self, *, target, name, daemon):
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False
            self.joined = False
            workers.append(self)

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.joined = True

    monkeypatch.setattr("backend.app.main.threading.Thread", Worker)

    with TestClient(create_app(Settings(local_scheduler_enabled=False))):
        assert workers == []

    with TestClient(create_app(Settings(local_scheduler_enabled=True))):
        assert len(workers) == 1
        assert workers[0].started
        assert workers[0].name == "bhashalearn-local-reminder-scheduler"

    assert workers[0].joined
