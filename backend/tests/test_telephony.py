import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import CallAttempt, ReminderEvent, ReminderPreference
from app.settings import settings
from app.telephony import classify_sip_failure, start_outbound_reminder_call, telephony_blockers


def test_telephony_requires_all_gates_and_verified_test_number(monkeypatch):
    for name in ("livekit_url", "livekit_api_key", "livekit_api_secret", "sip_outbound_trunk_id", "sip_caller_id", "verified_test_numbers"):
        monkeypatch.setattr(settings, name, "")
    monkeypatch.setattr(settings, "allow_test_calls", False)
    assert "VERIFIED_TEST_NUMBERS allowlist" in telephony_blockers(None)
    assert "ALLOW_TEST_CALLS=true" in telephony_blockers(None)


@pytest.mark.parametrize("code,expected", [(486, "busy"), (603, "rejected"), (480, "no_answer"), (503, "failed")])
def test_sip_failure_codes_map_to_call_status(code, expected):
    error = RuntimeError("SIP error")
    error.sip_status_code = code
    assert classify_sip_failure(error) == expected


def test_dispatch_creates_sip_participant_once_and_records_attempt(scheduler_db, monkeypatch):
    factory, _, ids = scheduler_db
    for name, value in {
        "livekit_url": "https://lk.example.invalid", "livekit_api_key": "mock-key",
        "livekit_api_secret": "mock-only-secret-with-at-least-32-bytes", "sip_outbound_trunk_id": "trunk-test",
        "sip_caller_id": "+15550000002", "verified_test_numbers": "+15550000001",
        "livekit_agent_name": "test-worker", "call_start_hour": 0, "call_end_hour": 24,
        "max_calls_per_day": 3,
    }.items():
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(settings, "allow_test_calls", True)
    with factory.begin() as db:
        db.add(ReminderPreference(student_id=ids["student_id"], timezone="UTC", language="en-IN",
            call_enabled=True, call_consent_at=datetime.now(timezone.utc), phone_e164="+15550000001",
            phone_verified_at=datetime.now(timezone.utc)))

    calls = []

    class Service:
        async def create_room(self, request):
            calls.append(("room", request.name))

        async def create_dispatch(self, request):
            calls.append(("agent", request.agent_name, request.room))

        async def create_sip_participant(self, request):
            calls.append(("sip", request.sip_trunk_id, request.sip_call_to, request.sip_number))

    class FakeLiveKitAPI:
        def __init__(self, *_):
            self.room = Service()
            self.agent_dispatch = Service()
            self.sip = Service()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr("app.telephony.api.LiveKitAPI", FakeLiveKitAPI)
    with factory() as db:
        result = asyncio.run(start_outbound_reminder_call(db, ids["student_id"], ids["reminder_id"]))
        assert result["status"] == "ringing" and result["duplicate"] is False
        duplicate = asyncio.run(start_outbound_reminder_call(db, ids["student_id"], ids["reminder_id"]))
        assert duplicate["duplicate"] is True
        row = db.get(CallAttempt, UUID(result["call_id"]))
        assert row.status == "ringing"
        event_names = {e.event for e in db.scalars(select(ReminderEvent).where(ReminderEvent.reminder_id == ids["reminder_id"]))}
        assert "outbound_call_ringing" in event_names
    assert [call[0] for call in calls].count("sip") == 1
    assert next(call for call in calls if call[0] == "sip")[1:] == ("trunk-test", "+15550000001", "+15550000002")


def test_sip_dispatch_fails_closed_without_student_consent(scheduler_db, monkeypatch):
    factory, _, ids = scheduler_db
    monkeypatch.setattr(settings, "allow_test_calls", True)
    with factory() as db:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(start_outbound_reminder_call(db, ids["student_id"], ids["reminder_id"]))
    assert exc.value.status_code == 503
    assert "active student call consent" in exc.value.detail["missing"]
