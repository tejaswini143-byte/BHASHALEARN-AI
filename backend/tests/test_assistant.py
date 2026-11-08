"""INT17 contracts using a disposable per-test SQLite database and mock providers."""
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import AssistantJob
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.assistant_worker import run_due_jobs
from backend.app.services.assistant_worker import _quiet_end_utc
from backend.app.db.models import AssistantSettings
from backend.app.db.models import AssistantAccount, AssistantCallAttempt, AssistantDraft
from urllib.parse import urlparse, parse_qs


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'int17.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    def override_db():
        with factory() as db: yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client: yield client, factory
    app.dependency_overrides.clear(); engine.dispose(); get_settings.cache_clear()


def login(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Test learner", "password": password}).status_code == 201
    result = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def test_settings_and_deadlines_are_owner_scoped_and_idempotent(env):
    client, _ = env
    owner = login(client, "owner@example.com"); other = login(client, "other@example.com")
    saved = client.patch("/api/v1/assistant/settings", headers=owner, json={"modes": ["student", "personal"], "timezone": "America/Los_Angeles", "preferred_language": "te", "notifications": {"email": False}})
    assert saved.status_code == 200 and saved.json()["modes"] == ["student", "personal"]
    assert saved.json()["notifications"] == {"email": False, "call": False}
    due = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
    data = {"title": "Exam", "due_at": due, "timezone": "America/Los_Angeles"}
    first = client.post("/api/v1/assistant/deadlines", headers=owner, json=data)
    second = client.post("/api/v1/assistant/deadlines", headers=owner, json=data)
    assert first.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert client.get("/api/v1/assistant/deadlines", headers=other).json() == []
    assert client.post(f"/api/v1/assistant/deadlines/{first.json()['id']}/complete", headers=other).status_code == 404
    assert client.get("/api/v1/assistant/settings", headers=other).json()["modes"] == ["student"]


def test_deadline_rejects_timezone_naive_datetime(env):
    client, _ = env; headers = login(client, "dates@example.com")
    result = client.post("/api/v1/assistant/deadlines", headers=headers, json={"title": "No guessed time", "due_at": "2030-01-01T09:00:00"})
    assert result.status_code == 422


def test_call_consent_needs_verified_number_and_phone_change_clears_it(env):
    client, _ = env; headers = login(client, "calls@example.com")
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"call_consent": True}).status_code == 409


def test_auto_reply_stays_disabled_until_rules_and_provider_exist(env):
    client, _ = env; headers = login(client, "policy@example.com")
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"email_policy": "auto_rules"}).status_code == 409
    assert client.get("/api/v1/assistant/settings", headers=headers).json()["email_policy"] == "draft_only"


def test_edit_deadline_reschedules_persisted_jobs(env):
    client, factory = env; headers = login(client, "edit@example.com")
    due = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={"title": "Initial", "due_at": due}).json()
    updated_due = (datetime.now(timezone.utc) + timedelta(days=8)).replace(microsecond=0).isoformat()
    result = client.patch(f"/api/v1/assistant/deadlines/{deadline['id']}", headers=headers, json={"title": "Revised", "due_at": updated_due})
    assert result.status_code == 200 and result.json()["title"] == "Revised"
    with factory() as db:
        jobs = db.scalars(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"])).all()
        assert any(job.status == "canceled" for job in jobs)
        assert any(job.status == "queued" and job.idempotency_key.startswith("deadline:" + deadline["id"] + ":edit:") for job in jobs)
    bad_phone = client.patch("/api/v1/assistant/settings", headers=headers, json={"reminder_phone": "5550101"})
    assert bad_phone.status_code == 422
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"reminder_phone": "+15551234567"}).status_code == 200
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"call_consent": True}).status_code == 409


def test_email_send_requires_approval_and_even_approved_draft_stays_unsent(env):
    client, _ = env; headers = login(client, "email@example.com")
    created = client.post("/api/v1/assistant/drafts", headers=headers, json={"thread_ref": "thread-1", "recipient": "peer@example.com", "subject": "Hello", "body": "Thanks."})
    assert created.status_code == 201
    draft_id = created.json()["id"]
    send_headers = {**headers, "Idempotency-Key": "draft-send-attempt-0001"}
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers=send_headers).status_code == 409
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/approve", headers=headers).json()["status"] == "approved"
    result = client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers=send_headers)
    assert result.status_code == 503 and "approved draft remains unsent" in result.json()["detail"]
    assert client.get("/api/v1/assistant/drafts", headers=headers).json()[0]["status"] == "approved"


def test_high_risk_draft_requires_individual_approval_and_live_provider(env):
    client, _ = env; headers = login(client, "risk@example.com")
    draft = client.post("/api/v1/assistant/drafts", headers=headers, json={"thread_ref": "thread-2", "recipient": "peer@example.com", "subject": "Offer", "body": "I accept", "risk_category": "employment"}).json()
    key = {**headers, "Idempotency-Key": "high-risk-send-0001"}
    assert client.post(f"/api/v1/assistant/drafts/{draft['id']}/send", headers=key).status_code == 409
    client.post(f"/api/v1/assistant/drafts/{draft['id']}/approve", headers=headers)
    assert client.post(f"/api/v1/assistant/drafts/{draft['id']}/send", headers=key).status_code == 503


def test_worker_persists_mock_outcome_respects_pause_and_quiet_hours(env):
    client, factory = env; headers = login(client, "worker@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={"paused": True, "reminder_lead_minutes": [0]})
    due = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={"title": "Study", "due_at": due}).json()
    with factory() as db:
        job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"]))
        job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
        assert run_due_jobs(db) == 0
        db.refresh(job); assert job.status == "queued"
    client.patch("/api/v1/assistant/settings", headers=headers, json={"paused": False})
    with factory() as db:
        job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"]))
        assert run_due_jobs(db) == 1
        db.refresh(job); assert job.status == "completed" and job.provider_status == "mocked" and job.attempts == 1


def test_integrations_are_explicitly_unavailable_and_no_gmail_data_exposed(env):
    client, _ = env; headers = login(client, "provider@example.com")
    result = client.get("/api/v1/assistant/integrations", headers=headers)
    assert result.status_code == 200
    assert all(item["status"] == "disconnected" and item["available"] is False for item in result.json())
    assert client.get("/api/v1/assistant/activity", headers=headers).json() == []


def test_quiet_hours_follow_daylight_saving_transitions():
    settings = AssistantSettings(student_id="student", timezone_name="America/New_York", quiet_start="22:00", quiet_end="07:00")
    spring_now = datetime.fromisoformat("2026-03-08T06:30:00+00:00")
    assert _quiet_end_utc(spring_now, settings) == datetime.fromisoformat("2026-03-08T11:00:00+00:00")
    settings.quiet_start = "01:00"; settings.quiet_end = "01:45"
    fall_second_fold = datetime.fromisoformat("2026-11-01T06:30:00+00:00")
    assert _quiet_end_utc(fall_second_fold, settings) == datetime.fromisoformat("2026-11-01T06:45:00+00:00")


def test_oauth_state_is_owner_bound_one_time_and_replay_rejected(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, _ = env; headers = login(client, "oauth-state@example.com")
    monkeypatch.setattr(assistant_api, "google_ready", lambda *args, **kwargs: True)
    monkeypatch.setattr(assistant_api, "google_authorization_url", lambda provider, state, challenge: f"https://accounts.example.invalid/?state={state}")
    result = client.post("/api/v1/assistant/integrations/gmail/connect", headers=headers)
    assert result.status_code == 200
    state = parse_qs(urlparse(result.json()["authorization_url"]).query)["state"][0]
    denied = client.get("/api/v1/assistant/integrations/gmail/callback", params={"state": state, "error": "access_denied"})
    assert denied.status_code == 400
    replay = client.get("/api/v1/assistant/integrations/gmail/callback", params={"state": state, "error": "access_denied"})
    assert replay.status_code == 400


def test_twilio_call_is_claimed_once_and_persisted_before_provider_boundary(env, monkeypatch):
    from backend.app.services import assistant_worker
    from backend.app.config import Settings
    client, factory = env; headers = login(client, "call-idempotency@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={"reminder_phone": "+15551234567", "reminder_lead_minutes": [0]})
    due = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={"title": "Exam", "due_at": due}).json()
    with factory() as db:
        prefs = db.scalar(select(AssistantSettings))
        prefs.phone_verified = True; prefs.call_consent_at = datetime.now(timezone.utc)
        job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"]))
        job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    config = Settings(app_env="production", assistant_live_operations_enabled=True, twilio_live_calls_enabled=True,
        twilio_account_sid="ACfake", twilio_auth_token="fake", twilio_from_number="+15557654321",
        twilio_status_callback_url="https://assistant.example.invalid/callback", twilio_allowed_destination_prefixes="+1")
    calls = []
    monkeypatch.setattr(assistant_worker, "get_settings", lambda: config)
    monkeypatch.setattr(assistant_worker, "twilio_live_ready", lambda *args, **kwargs: True)
    monkeypatch.setattr(assistant_worker, "twilio_create_call", lambda *args, **kwargs: (calls.append(args) or {"sid": "CAfake", "status": "queued"}))
    with factory() as db:
        assert run_due_jobs(db, allow_live_operations=True) == 1
        assert run_due_jobs(db, allow_live_operations=True) == 0
        assert len(calls) == 1
        attempt = db.scalar(select(AssistantCallAttempt).where(AssistantCallAttempt.job_id == job.id))
        assert attempt is not None and attempt.provider_sid == "CAfake"
        assert attempt.destination == "+15551234567"


def test_gmail_send_requires_approval_is_idempotent_and_owner_scoped(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env; owner = login(client, "send-owner@example.com"); other = login(client, "send-other@example.com")
    created = client.post("/api/v1/assistant/drafts", headers=owner, json={
        "thread_ref": "thread-safe", "recipient": "peer@example.com", "subject": "Hello", "body": "Thanks."})
    assert created.status_code == 201
    draft_id = created.json()["id"]
    with factory() as db:
        draft = db.get(AssistantDraft, draft_id)
        db.add(AssistantAccount(student_id=draft.student_id, provider="gmail", status="connected",
            granted_scopes='["https://www.googleapis.com/auth/gmail.send"]'))
        db.commit()
    sent = []
    monkeypatch.setattr(assistant_api, "google_ready", lambda *args, **kwargs: True)
    monkeypatch.setattr(assistant_api, "send_gmail_draft", lambda *args, **kwargs: (sent.append(True) or {"message_id": "msg-confirmed", "thread_id": "thread-safe"}))
    key = {**owner, "Idempotency-Key": "idempotent-send-key-0001"}
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers=key).status_code == 409
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/approve", headers=owner).status_code == 200
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers=key).json()["status"] == "sent"
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers={**owner, "Idempotency-Key": "second-send-key-00002"}).json()["provider_message_id"] == "msg-confirmed"
    assert len(sent) == 1
    assert client.post(f"/api/v1/assistant/drafts/{draft_id}/send", headers={**other, "Idempotency-Key": "other-user-send-key"}).status_code == 404


def test_signed_twilio_callback_updates_lifecycle_and_rejects_replay(env, monkeypatch):
    import base64, hashlib, hmac
    from backend.app.api import assistant as assistant_api
    from backend.app.config import Settings
    from backend.app.db.models import Student
    client, factory = env; owner = login(client, "callback-owner@example.com")
    with factory() as db:
        user = db.scalar(select(Student).where(Student.email == "callback-owner@example.com"))
        job = AssistantJob(student_id=user.id, kind="reminder", status="waiting_callback", run_at=datetime.now(timezone.utc), idempotency_key="callback-job-key", attempts=1, max_attempts=3)
        db.add(job); db.flush()
        attempt = AssistantCallAttempt(student_id=user.id, job_id=job.id, attempt_number=1,
            idempotency_key="callback-attempt-key", destination="+15551234567", status="ringing", provider_sid="CAcallback", provider_status="ringing")
        db.add(attempt); db.commit()
        job_id = job.id; attempt_id = attempt.id
    cfg = Settings(app_env="production", assistant_live_operations_enabled=True, twilio_live_calls_enabled=True,
        twilio_account_sid="ACfake", twilio_auth_token="callback-secret",
        twilio_from_number="+15557654321", twilio_status_callback_url="https://assistant.example.invalid/api/v1/assistant/webhooks/twilio/status")
    monkeypatch.setattr(assistant_api, "get_settings", lambda: cfg)
    monkeypatch.setattr(assistant_api, "twilio_live_ready", lambda *args, **kwargs: True)
    payload = {"AccountSid": "ACfake", "CallSid": "CAcallback", "To": "+15551234567", "CallStatus": "completed"}
    raw = cfg.twilio_status_callback_url + "".join(key + payload[key] for key in sorted(payload))
    signature = base64.b64encode(hmac.new(cfg.twilio_auth_token.encode(), raw.encode(), hashlib.sha1).digest()).decode()
    endpoint = "/api/v1/assistant/webhooks/twilio/status"
    first = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": signature})
    replay = client.post(endpoint, data=payload, headers={"X-Twilio-Signature": signature})
    assert first.status_code == 200 and replay.json()["duplicate"] is True
    with factory() as db:
        assert db.get(AssistantJob, job_id).status == "completed"
        assert db.get(AssistantCallAttempt, attempt_id).provider_status == "completed"
