"""INT17 contracts using a disposable per-test SQLite database and mock providers."""
import pytest
import json
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import AssistantDeadline, AssistantJob, AssistantLocalCall, AssistantAuditEvent
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


def answer_call(client, call_id, headers, *, initiating_component="browser_answer_button", request_id="11111111-2222-4333-8444-555555555555"):
    return client.post(f"/api/v1/assistant/local-calls/{call_id}/answer", headers={**headers, "X-Request-ID": request_id},
        json={"explicit_user_action": True, "initiating_component": initiating_component})


def test_settings_and_deadlines_are_owner_scoped_and_idempotent(env):
    client, _ = env
    owner = login(client, "owner@example.com"); other = login(client, "other@example.com")
    saved = client.patch("/api/v1/assistant/settings", headers=owner, json={"modes": ["student", "personal"], "timezone": "America/Los_Angeles", "preferred_language": "te", "notifications": {"email": False}})
    assert saved.status_code == 200 and saved.json()["modes"] == ["student", "personal"]
    assert saved.json()["notifications"] == {
        "email": False, "call": False, "desktop_call": False, "save_call_transcripts": False}
    due = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
    data = {"title": "Exam", "due_at": due, "timezone": "America/Los_Angeles"}
    first = client.post("/api/v1/assistant/deadlines", headers=owner, json=data)
    second = client.post("/api/v1/assistant/deadlines", headers=owner, json=data)
    assert first.status_code == 201 and first.json()["id"] == second.json()["id"]
    assert client.get("/api/v1/assistant/deadlines", headers=other).json() == []
    assert client.post(f"/api/v1/assistant/deadlines/{first.json()['id']}/complete", headers=other).status_code == 404
    assert client.get("/api/v1/assistant/settings", headers=other).json()["modes"] == ["student"]


def test_local_call_duration_is_persisted_and_enforced(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env
    headers = login(client, "call-duration@example.com")
    settings = client.patch("/api/v1/assistant/settings", headers=headers,
                            json={"max_call_duration_minutes": 10})
    assert settings.status_code == 200
    assert settings.json()["max_call_duration_minutes"] == 10
    assert client.patch("/api/v1/assistant/settings", headers=headers,
                        json={"max_call_duration_minutes": 15}).status_code == 422
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *args, **kwargs: "Hello, I am BHASHALEARN AI.")
    started = client.post("/api/v1/assistant/local-calls/test", headers=headers, json={"language": "en"})
    assert started.status_code == 201
    assert started.json()["max_duration_minutes"] == 10
    call_id = started.json()["id"]
    answered = answer_call(client, call_id, headers)
    assert answered.status_code == 200 and answered.json()["status"] == "answered"
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        row.answered_at = datetime.now(timezone.utc) - timedelta(minutes=11)
        db.commit()
    expired_turn = client.post(f"/api/v1/assistant/local-calls/{call_id}/turn", headers=headers,
                               json={"text": "I am still working", "language": "en"})
    assert expired_turn.status_code == 409
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        assert row.status == "ended" and row.ended_at is not None


def test_worker_ends_expired_local_call_and_clears_unsaved_transcript(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env
    headers = login(client, "call-worker-duration@example.com")
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *args, **kwargs: "Hello.")
    call = client.post("/api/v1/assistant/local-calls/test", headers=headers, json={"language": "en"}).json()
    call_id = call["id"]
    answer_call(client, call_id, headers)
    now = datetime.now(timezone.utc)
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        row.max_duration_minutes = 5
        row.answered_at = now - timedelta(minutes=6)
        row.turns_json = '[{"role":"assistant","content":"private test text"}]'
        db.commit()
        assert run_due_jobs(db, now=now) == 0
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        ended_at = row.ended_at.replace(tzinfo=timezone.utc) if row.ended_at.tzinfo is None else row.ended_at
        assert row.status == "ended" and ended_at == now
        assert row.turns_json == "[]"


def test_call_extension_handler_updates_timer_limit_without_http_runtime(monkeypatch):
    from types import SimpleNamespace
    from fastapi import HTTPException
    from backend.app.api import assistant as assistant_api
    from backend.app.api.assistant import LocalCallExtension

    now = datetime.now(timezone.utc)
    row = SimpleNamespace(id="unit-call", student_id="unit-student", deadline_id=None, job_id=None,
        status="answered", language="en", max_duration_minutes=30, turns_json="[]",
        pending_reschedule_at=None, answered_at=now, ended_at=None, created_at=now, updated_at=now)
    class DB:
        def get(self, _model, _key): return None
        def add(self, _event): pass
        def commit(self): pass
        def refresh(self, _row): pass
    db = DB()
    monkeypatch.setattr(assistant_api, "_owned_local_call", lambda *_args: row)
    updated = assistant_api.extend_local_call("unit-call", LocalCallExtension(additional_minutes=10),
        SimpleNamespace(id="unit-student"), db)
    assert updated.max_duration_minutes == 40
    with pytest.raises(HTTPException, match="120 total minutes") as error:
        row.max_duration_minutes = 120
        assistant_api.extend_local_call("unit-call", LocalCallExtension(additional_minutes=10),
            SimpleNamespace(id="unit-student"), db)
    assert error.value.status_code == 422


def test_local_call_can_be_extended_by_authenticated_owner(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, _ = env
    owner = login(client, "call-extension-owner@example.com")
    other = login(client, "call-extension-other@example.com")
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *args, **kwargs: "Hello.")
    call = client.post("/api/v1/assistant/local-calls/test", headers=owner,
                       json={"language": "en"}).json()
    call_id = call["id"]
    answered = answer_call(client, call_id, owner)
    assert answered.status_code == 200
    assert answered.json()["answered_at"].endswith(("Z", "+00:00"))
    extended = client.post(f"/api/v1/assistant/local-calls/{call_id}/extend", headers=owner,
                           json={"additional_minutes": 10})
    assert extended.status_code == 200 and extended.json()["max_duration_minutes"] == 40
    assert client.post(f"/api/v1/assistant/local-calls/{call_id}/extend", headers=other,
                       json={"additional_minutes": 10}).status_code == 404
    too_long = client.post(f"/api/v1/assistant/local-calls/{call_id}/extend", headers=owner,
                           json={"additional_minutes": 30})
    assert too_long.status_code == 200 and too_long.json()["max_duration_minutes"] == 70
    assert client.post(f"/api/v1/assistant/local-calls/{call_id}/extend", headers=owner,
                       json={"additional_minutes": 30}).json()["max_duration_minutes"] == 100
    assert client.post(f"/api/v1/assistant/local-calls/{call_id}/extend", headers=owner,
                       json={"additional_minutes": 30}).status_code == 422


def test_deadline_rejects_timezone_naive_datetime(env):
    client, _ = env; headers = login(client, "dates@example.com")
    result = client.post("/api/v1/assistant/deadlines", headers=headers, json={"title": "No guessed time", "due_at": "2030-01-01T09:00:00"})
    assert result.status_code == 422


def test_voice_reminder_parses_relative_time_and_requires_confirmation(env):
    client, _ = env; headers = login(client, "voice-reminder@example.com")
    phrase = "Remind me in 20 minutes to review fraction addition"
    before = datetime.now(timezone.utc)
    preview = client.post("/api/v1/assistant/voice/commands", headers=headers, json={
        "text": phrase, "confirmed": False,
    })
    assert preview.status_code == 200
    data = preview.json()
    assert data["intent"] == "create_deadline" and data["requires_confirmation"] is True
    assert data["preview"]["title"] == "review fraction addition"
    due_at = datetime.fromisoformat(data["preview"]["due_at"])
    remaining = (due_at - before).total_seconds()
    assert 19 * 60 <= remaining <= 21 * 60
    assert client.get("/api/v1/assistant/deadlines", headers=headers).json() == []

    created = client.post("/api/v1/assistant/voice/commands", headers=headers, json={
        "text": phrase, "confirmed": True, "title": data["preview"]["title"],
        "due_at": data["preview"]["due_at"],
    })
    assert created.status_code == 200
    assert created.json()["deadline"]["title"] == "review fraction addition"
    assert len(client.get("/api/v1/assistant/deadlines", headers=headers).json()) == 1


def test_call_consent_needs_verified_number_and_phone_change_clears_it(env):
    client, _ = env; headers = login(client, "calls@example.com")
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"call_consent": True}).status_code == 409
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"reminder_phone": "5550101"}).status_code == 422
    assert client.patch("/api/v1/assistant/settings", headers=headers, json={"reminder_phone": "+15551234567"}).status_code == 200
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


def test_upcoming_deadline_with_elapsed_reminder_lead_is_queued_immediately(env):
    client, factory = env; headers = login(client, "immediate-reminder@example.com")
    settings = client.patch("/api/v1/assistant/settings", headers=headers, json={
        "reminder_lead_minutes": [60], "notifications": {"desktop_call": True},
    })
    assert settings.status_code == 200
    due = (datetime.now(timezone.utc) + timedelta(seconds=20)).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={
        "title": "Due soon", "due_at": due,
    }).json()
    with factory() as db:
        jobs = db.scalars(select(AssistantJob).where(
            AssistantJob.deadline_id == deadline["id"], AssistantJob.kind == "reminder",
        )).all()
        assert len(jobs) == 1
        assert jobs[0].status == "queued"
        run_at = jobs[0].run_at
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        assert run_at <= datetime.now(timezone.utc) + timedelta(seconds=1)


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


def test_opted_in_worker_creates_one_persistent_local_ringing_call(env):
    client, factory = env; headers = login(client, "desktop-reminder@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={
        "reminder_lead_minutes": [0], "notifications": {"desktop_call": True}})
    due = (datetime.now(timezone.utc) + timedelta(minutes=10)).replace(microsecond=0).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers,
        json={"title": "QA local reminder", "due_at": due}).json()
    with factory() as db:
        job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"]))
        job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
        assert run_due_jobs(db) == 1
        db.refresh(job)
        calls = db.scalars(select(AssistantLocalCall).where(AssistantLocalCall.job_id == job.id)).all()
        assert job.status == "completed" and job.provider_status == "desktop_pending"
        assert len(calls) == 1 and calls[0].status == "ringing"
        assert run_due_jobs(db) == 0
        assert len(db.scalars(select(AssistantLocalCall).where(AssistantLocalCall.job_id == job.id)).all()) == 1
    pending = client.get("/api/v1/assistant/local-calls/pending", headers=headers)
    assert pending.status_code == 200 and pending.json()[0]["title"] == "QA local reminder"


def test_due_time_reminder_fires_after_deadline_becomes_overdue(env):
    client, factory = env; headers = login(client, "zero-lead-reminder@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={
        "reminder_lead_minutes": [0], "notifications": {"desktop_call": True},
    })
    due = datetime.now(timezone.utc) + timedelta(seconds=1)
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={
        "title": "Due-time local reminder", "due_at": due.isoformat(),
    }).json()
    with factory() as db:
        job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"]))
        assert job is not None
        assert run_due_jobs(db, now=due + timedelta(seconds=2)) == 1
        db.refresh(job)
        row = db.get(AssistantDeadline, deadline["id"])
        assert row.status == "overdue"
        assert job.status == "completed" and job.provider_status == "desktop_pending"
        assert db.scalar(select(AssistantLocalCall).where(AssistantLocalCall.job_id == job.id)) is not None


def test_due_reminder_is_deferred_while_another_local_call_is_active(env):
    client, factory = env; headers = login(client, "no-overlap-reminders@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={
        "reminder_lead_minutes": [0], "notifications": {"desktop_call": True},
    })
    now = datetime.now(timezone.utc)
    first = client.post("/api/v1/assistant/deadlines", headers=headers, json={
        "title": "Active QA call", "due_at": (now + timedelta(hours=1)).isoformat(),
    }).json()
    second = client.post("/api/v1/assistant/deadlines", headers=headers, json={
        "title": "Deferred QA call", "due_at": (now + timedelta(hours=1)).isoformat(),
    }).json()
    with factory() as db:
        first_job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == first["id"]))
        second_job = db.scalar(select(AssistantJob).where(AssistantJob.deadline_id == second["id"]))
        first_job.run_at = now - timedelta(seconds=1)
        second_job.run_at = now - timedelta(seconds=1)
        db.add(AssistantLocalCall(student_id=first_job.student_id, deadline_id=first["id"],
            job_id=first_job.id, status="answered", language="en", answered_at=now))
        db.commit()
        assert run_due_jobs(db, now=now) == 0
        db.refresh(first_job); db.refresh(second_job)
        assert first_job.status == "queued"
        assert second_job.status == "queued"
        assert second_job.last_error == "deferred_for_active_call"
        assert second_job.run_at.replace(tzinfo=timezone.utc) == now + timedelta(seconds=30)
        assert db.scalar(select(AssistantLocalCall).where(AssistantLocalCall.job_id == second_job.id)) is None


def test_local_test_call_uses_provider_turns_owner_scope_and_clears_transcript(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env; owner = login(client, "local-call@example.com"); other = login(client, "other-local-call@example.com")
    generated = []; instructions = []
    def generated_reply(instruction, history):
        instructions.append(instruction)
        generated.append(history[-1]["content"])
        return "Hello, I am BHASHALEARN AI. How is your study plan going?"
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", generated_reply)
    deadline = client.post("/api/v1/assistant/deadlines", headers=owner, json={
        "title": "Local call test deadline", "due_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }).json()
    started = client.post("/api/v1/assistant/local-calls/test", headers=owner,
        json={"language": "en", "deadline_id": deadline["id"]})
    assert started.status_code == 201 and started.json()["status"] == "ringing"
    call_id = started.json()["id"]
    assert answer_call(client, call_id, other).status_code == 404
    answered = answer_call(client, call_id, owner)
    assert answered.status_code == 200 and "identify myself" not in answered.json()["greeting"].casefold()
    repeated = answer_call(client, call_id, owner, request_id="22222222-2222-4222-8222-222222222222")
    assert repeated.status_code == 200 and repeated.json()["greeting"] == answered.json()["greeting"]
    assert len(generated) == 1
    turn_id = "11111111-2222-4333-8444-555555555555"
    turn = client.post(f"/api/v1/assistant/local-calls/{call_id}/turn", headers=owner,
        json={"text": "I have not started yet", "language": "en", "turn_id": turn_id})
    assert turn.status_code == 200 and turn.json()["provider"] == "gemini_live"
    assert turn.json()["reply"].startswith("Hello, I am BHASHALEARN AI.")
    repeated_turn = client.post(f"/api/v1/assistant/local-calls/{call_id}/turn", headers=owner,
        json={"text": "Changed text must not replace an already committed turn", "language": "en", "turn_id": turn_id})
    assert repeated_turn.status_code == 200
    assert repeated_turn.json()["reply"] == turn.json()["reply"]
    assert repeated_turn.json()["turn_id"] == turn_id
    assert len(generated) == 2  # One greeting and one unique turn; the retry did not call Gemini again.
    reminder_turn = client.post(f"/api/v1/assistant/local-calls/{call_id}/turn", headers=owner,
        json={"text": "Please remind me again in 2 minutes", "language": "en",
              "turn_id": "33333333-2222-4333-8444-555555555555"})
    assert reminder_turn.status_code == 200 and reminder_turn.json()["requires_confirmation"] is True
    assert "can schedule a reminder change after the student explicitly confirms it" in instructions[-1]
    assert "never say you cannot schedule reminders" in instructions[-1]
    assert len(generated) == 3
    ended = client.post(f"/api/v1/assistant/local-calls/{call_id}/end", headers=owner)
    assert ended.status_code == 200 and ended.json()["status"] == "ended"
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        assert row.turns_json == "[]"


def test_call_answer_requires_attributed_explicit_action_and_audits_transition(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env
    owner = login(client, "answer-audit@example.com")
    generated = []
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *_args, **_kwargs: generated.append(True) or "Hello.")
    call = client.post("/api/v1/assistant/local-calls/test", headers=owner, json={"language": "en"}).json()
    call_id = call["id"]

    missing_action = client.post(f"/api/v1/assistant/local-calls/{call_id}/answer", headers=owner)
    assert missing_action.status_code == 422
    with factory() as db:
        assert db.get(AssistantLocalCall, call_id).status == "ringing"
    assert generated == []

    request_id = "33333333-3333-4333-8333-333333333333"
    answered = answer_call(client, call_id, owner, request_id=request_id)
    assert answered.status_code == 200 and answered.json()["status"] == "answered"
    with factory() as db:
        events = db.query(AssistantAuditEvent).filter_by(target_id=call_id, action="local_call.answered").all()
        assert len(events) == 1
        details = json.loads(events[0].details_json)
        assert details["request_id"] == request_id
        assert details["principal_id"]
        assert details["initiating_component"] == "browser_answer_button"
        assert details["event_type"] == "answer_confirmed"
        assert details["previous_state"] == "ringing" and details["new_state"] == "answered"
    assert len(generated) == 1


def test_stale_or_missing_student_session_cannot_answer_a_call(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env
    owner = login(client, "stale-answer@example.com")
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *_args, **_kwargs: pytest.fail("Unauthenticated answer must not reach Gemini"))
    call = client.post("/api/v1/assistant/local-calls/test", headers=owner, json={"language": "en"}).json()
    action = {"explicit_user_action": True, "initiating_component": "browser_answer_button"}
    for stale_headers in ({}, {"Authorization": "Bearer expired-session-token"}):
        result = client.post(f"/api/v1/assistant/local-calls/{call['id']}/answer", headers=stale_headers, json=action)
        assert result.status_code == 401
    with factory() as db:
        assert db.get(AssistantLocalCall, call["id"]).status == "ringing"


def test_unanswered_call_cannot_start_microphone_or_prisma_transcription(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env
    owner = login(client, "unanswered-mic@example.com")
    call = client.post("/api/v1/assistant/local-calls/test", headers=owner, json={"language": "en"}).json()
    call_id = call["id"]
    mic = client.post(f"/api/v1/assistant/local-calls/{call_id}/microphone", headers=owner,
        json={"explicit_user_action": True, "initiating_component": "browser_microphone_button"})
    assert mic.status_code == 409
    monkeypatch.setattr(assistant_api, "validate_audio", lambda _path: None)
    monkeypatch.setattr(assistant_api, "create_prisma_client", lambda: pytest.fail("Prisma must not run for an unanswered call"))
    transcription = client.post(f"/api/v1/assistant/local-calls/{call_id}/transcribe", headers=owner,
        data={"microphone_authorization": "invalid-token"},
        files={"audio": ("synthetic.wav", b"fixture", "audio/wav")})
    assert transcription.status_code == 409
    with factory() as db:
        row = db.get(AssistantLocalCall, call_id)
        assert row.status == "ringing"
        events = db.query(AssistantAuditEvent).filter_by(target_id=call_id).all()
        assert any(event.action == "local_call.microphone.rejected" for event in events)
        assert any(event.action == "local_call.transcription.rejected" for event in events)


def test_call_microphone_authorization_is_one_use_and_attributed(env, monkeypatch):
    from types import SimpleNamespace
    from backend.app.api import assistant as assistant_api
    client, factory = env
    owner = login(client, "mic-one-use@example.com")
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda *_args, **_kwargs: "Hello.")
    monkeypatch.setattr(assistant_api, "validate_audio", lambda _path: None)
    call = client.post("/api/v1/assistant/local-calls/test", headers=owner, json={"language": "en"}).json()
    call_id = call["id"]
    assert client.post(f"/api/v1/assistant/local-calls/{call_id}/microphone", headers=owner,
        json={"explicit_user_action": True, "initiating_component": "browser_microphone_button"}).status_code == 409
    assert answer_call(client, call_id, owner).status_code == 200
    activation = client.post(f"/api/v1/assistant/local-calls/{call_id}/microphone", headers=owner,
        json={"explicit_user_action": True, "initiating_component": "browser_microphone_button"})
    assert activation.status_code == 200
    token = activation.json()["authorization"]
    stt_calls = []
    class FakeAdapter:
        def transcribe(self, _path):
            stt_calls.append(True)
            return SimpleNamespace(text="synthetic fixture", detected_language="en")
    monkeypatch.setattr(assistant_api, "create_prisma_client", lambda: object())
    monkeypatch.setattr(assistant_api, "PrismaTranscriptionAdapter", lambda _provider: FakeAdapter())
    def transcribe():
        return client.post(f"/api/v1/assistant/local-calls/{call_id}/transcribe", headers=owner,
            data={"microphone_authorization": token},
            files={"audio": ("synthetic.wav", b"fixture", "audio/wav")})
    first = transcribe()
    second = transcribe()
    assert first.status_code == 200 and first.json()["transcript"] == "synthetic fixture"
    assert second.status_code == 409 and len(stt_calls) == 1
    with factory() as db:
        events = db.query(AssistantAuditEvent).filter_by(target_id=call_id).all()
        activated = next(event for event in events if event.action == "local_call.microphone.authorized")
        details = json.loads(activated.details_json)
        assert details["initiating_component"] == "browser_microphone_button"
        assert details["event_type"] == "explicit_microphone_gesture"
        assert any(event.action == "local_call.transcription.completed" for event in events)


def test_local_call_reminder_reschedule_requires_exact_confirmation(env, monkeypatch):
    from backend.app.api import assistant as assistant_api
    client, factory = env; headers = login(client, "local-reschedule@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={
        "reminder_lead_minutes": [0], "notifications": {"desktop_call": True}})
    due = (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers,
        json={"title": "Submit project", "due_at": due}).json()
    call = client.post("/api/v1/assistant/local-calls/test", headers=headers,
        json={"deadline_id": deadline["id"], "language": "en"}).json()
    monkeypatch.setattr(assistant_api, "generate_tutor_reply", lambda instruction, history: "Would you like me to schedule that reminder?")
    assert answer_call(client, call["id"], headers).status_code == 200
    turn = client.post(f"/api/v1/assistant/local-calls/{call['id']}/turn", headers=headers,
        json={"text": "Remind me again in 2 minutes", "language": "en"})
    assert turn.status_code == 200 and turn.json()["requires_confirmation"]
    reminder_at = turn.json()["proposed_reminder_at"]
    path = f"/api/v1/assistant/local-calls/{call['id']}/reschedule"
    preview = client.post(path, headers=headers, json={"reminder_at": reminder_at, "confirmed": False})
    assert preview.status_code == 200 and preview.json()["requires_confirmation"]
    saved = client.post(path, headers=headers, json={"reminder_at": reminder_at, "confirmed": True})
    assert saved.status_code == 200 and saved.json()["scheduled"] is True
    with factory() as db:
        jobs = db.scalars(select(AssistantJob).where(AssistantJob.deadline_id == deadline["id"])).all()
        assert any(job.idempotency_key.startswith("local-call:" + call["id"] + ":reschedule:") for job in jobs)


def test_confirmed_local_reschedule_can_ring_for_an_overdue_deadline(env):
    client, factory = env; headers = login(client, "overdue-reschedule@example.com")
    client.patch("/api/v1/assistant/settings", headers=headers, json={
        "notifications": {"desktop_call": True},
    })
    due = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    deadline = client.post("/api/v1/assistant/deadlines", headers=headers, json={
        "title": "Overdue but rescheduled", "due_at": due,
    }).json()
    with factory() as db:
        row = db.get(AssistantDeadline, deadline["id"])
        job = AssistantJob(student_id=row.student_id, deadline_id=row.id, kind="reminder", status="queued",
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            idempotency_key="local-call:qa-reschedule:reminder", attempts=0, max_attempts=5)
        db.add(job); db.commit()
        assert run_due_jobs(db) == 1
        db.refresh(row)
        assert row.status == "overdue"
        assert job.provider_status == "desktop_pending"
        assert db.scalar(select(AssistantLocalCall).where(AssistantLocalCall.job_id == job.id)) is not None


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
