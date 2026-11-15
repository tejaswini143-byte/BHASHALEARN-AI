import asyncio
from uuid import UUID
from sqlalchemy import select

from app.livekit_voice import create_browser_voice_session, livekit_blockers
from app.models import ReminderEvent, VoiceSession
from app.settings import settings


def test_missing_live_services_are_reported_without_attempting_dispatch(monkeypatch):
    for name in ("livekit_url", "livekit_api_key", "livekit_api_secret", "gemini_api_key", "gnani_api_key"):
        monkeypatch.setattr(settings, name, "")
    assert livekit_blockers() == ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "GEMINI_API_KEY", "GNANI_API_KEY"]


def test_browser_session_creates_room_dispatches_agent_and_issues_scoped_token(scheduler_db, monkeypatch):
    factory, _, ids = scheduler_db
    for name, value in {
        "livekit_url": "wss://lk.example.invalid", "livekit_api_key": "test-key",
        "livekit_api_secret": "mock-only-secret-with-at-least-32-bytes", "gemini_api_key": "test-gemini",
        "gnani_api_key": "test-gnani", "livekit_agent_name": "test-worker",
    }.items():
        monkeypatch.setattr(settings, name, value)
    calls = []

    class RoomService:
        async def create_room(self, request):
            calls.append(("room", request.name))

    class DispatchService:
        async def create_dispatch(self, request):
            calls.append(("dispatch", request.agent_name, request.room))

    class FakeLiveKitAPI:
        def __init__(self, *args):
            assert args == (settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret)
            self.room = RoomService()
            self.agent_dispatch = DispatchService()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr("app.livekit_voice.api.LiveKitAPI", FakeLiveKitAPI)
    with factory() as db:
        response = asyncio.run(create_browser_voice_session(db, ids["student_id"], ids["reminder_id"], "te-IN"))
        assert response["status"] == "dispatched"
        assert response["server_url"] == settings.livekit_url
        assert response["participant_token"]
        assert response["expires_in_seconds"] == 600
    assert calls[0][0] == "room"
    assert calls[1][0:2] == ("dispatch", "test-worker")
    with factory() as db:
        session = db.get(VoiceSession, UUID(response["session_id"]))
        assert session.status == "dispatched"
        events = list(db.scalars(select(ReminderEvent).where(ReminderEvent.reminder_id == ids["reminder_id"])))
        assert "voice_agent_dispatched" in {event.event for event in events}
