from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
import app.api as api
import app.scheduler as scheduler
from app.main import app
from app.models import Reminder
from app.scheduler import dispatch_browser_reminder
from sqlalchemy import select


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(api, "SessionLocal", factory)
    monkeypatch.setattr(scheduler, "SessionLocal", factory)
    async def idle_scheduler(stop):
        await stop.wait()
    monkeypatch.setattr(scheduler, "run_scheduler", idle_scheduler)
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()


def register(client, email):
    response = client.post("/api/auth/register", json={"email": email, "password": "A-strong-demo-password-123"})
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_demo_login_and_invalid_password(client):
    register(client, "learner@example.com")
    valid = client.post("/api/auth/login", json={"email": "learner@example.com", "password": "A-strong-demo-password-123"})
    invalid = client.post("/api/auth/login", json={"email": "learner@example.com", "password": "wrong"})
    assert valid.status_code == 200
    assert invalid.status_code == 401


def test_deadline_api_requires_auth_and_hides_other_students(client):
    owner = register(client, "owner@example.com")
    other = register(client, "other@example.com")
    unauthenticated = client.get("/api/deadlines")
    assert unauthenticated.status_code == 401
    created = client.post("/api/deadlines", headers={"Authorization": f"Bearer {owner}"}, json={
        "title": "Assignment", "kind": "assignment",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(), "timezone": "Asia/Kolkata"
    })
    assert created.status_code == 201, created.text
    deadline_id = created.json()["id"]
    forbidden = client.patch(f"/api/deadlines/{deadline_id}", headers={"Authorization": f"Bearer {other}"}, json={
        "title": "Changed", "kind": "assignment",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(), "timezone": "Asia/Kolkata"
    })
    assert forbidden.status_code == 404


@pytest.mark.parametrize("transcript", [
    "Remind me again in 30 minutes",
    "ముప్పై నిమిషాల తర్వాత గుర్తు చేయి",
])
def test_browser_reminder_end_to_end_snooze_persists_for_owner(client, transcript):
    token = register(client, "reminder-e2e@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post("/api/deadlines", headers=headers, json={
        "title": "Biology assignment", "kind": "assignment",
        "due_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "timezone": "Asia/Kolkata", "reminder_minutes_before": 60
    })
    assert created.status_code == 201, created.text
    with api.SessionLocal() as db:
        reminder = db.scalar(select(Reminder).where(Reminder.deadline_id == UUID(created.json()["id"])))
        assert reminder is not None
        reminder_id = reminder.id
        reminder.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert scheduler.claim_due_batch() == [str(reminder_id)]
    dispatch_browser_reminder(str(reminder_id))
    due_rows = client.get("/api/reminders", headers=headers).json()
    assert next(row for row in due_rows if row["id"] == str(reminder_id))["status"] == "in_progress"
    turn = client.post(f"/api/reminders/{reminder_id}/voice-turn", headers=headers,
                       json={"transcript": transcript})
    assert turn.status_code == 200, turn.text
    assert turn.json()["intent"] == "snooze"
    refreshed = client.get("/api/reminders", headers=headers).json()
    snoozed = next(row for row in refreshed if row["id"] == str(reminder_id))
    assert snoozed["status"] == "scheduled"
    assert snoozed["snoozed_until"]
