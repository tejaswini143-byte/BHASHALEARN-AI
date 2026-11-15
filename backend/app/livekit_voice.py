"""LiveKit room creation, least-privilege browser tokens, and explicit agent dispatch."""
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from livekit import api
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Reminder, ReminderEvent, ReminderPreference, VoiceSession
from .settings import settings


def livekit_blockers() -> list[str]:
    return [key for key, value in {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
        "GEMINI_API_KEY": settings.gemini_api_key,
        "GNANI_API_KEY": settings.gnani_api_key,
    }.items() if not value]


async def create_browser_voice_session(db: Session, student_id: UUID, reminder_id: UUID, language: str) -> dict:
    blockers = livekit_blockers()
    if blockers:
        raise HTTPException(503, {"message": "LiveKit voice is not configured", "missing": blockers})
    reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.student_id == student_id))
    if not reminder:
        raise HTTPException(404, "Reminder not found")
    if reminder.status not in {"in_progress", "notified", "scheduled"}:
        raise HTTPException(409, "Reminder is not available for a voice session")
    prefs = db.get(ReminderPreference, student_id)
    if prefs and (not prefs.voice_enabled or not prefs.reminders_enabled):
        raise HTTPException(403, "Voice reminders are disabled for this account")

    session_id = uuid4()
    room_name = f"deadline-{session_id.hex}"
    voice_session = VoiceSession(id=session_id, student_id=student_id, reminder_id=reminder_id,
                                 room_name=room_name, language=language, status="creating")
    db.add(voice_session)
    db.add(ReminderEvent(reminder_id=reminder_id, event="voice_session_creating", detail=str(session_id)))
    db.commit()

    try:
        async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
            await lk.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=60, max_participants=2))
            await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=settings.livekit_agent_name, room=room_name,
                metadata=json.dumps({"voice_session_id": str(session_id)})))
        token = (api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
                 .with_identity(f"student-{student_id}")
                 .with_name("BHASHALEARN student")
                 .with_ttl(timedelta(minutes=10))
                 .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True,
                                              can_subscribe=True, can_publish_data=True))
                 .to_jwt())
        voice_session.status = "dispatched"
        db.add(ReminderEvent(reminder_id=reminder_id, event="voice_agent_dispatched", detail=str(session_id)))
        db.commit()
        return {"session_id": str(session_id), "room_name": room_name, "server_url": settings.livekit_url,
                "participant_token": token, "expires_in_seconds": 600, "status": "dispatched"}
    except Exception as exc:
        db.rollback()
        failed = db.get(VoiceSession, session_id)
        if failed:
            failed.status = "failed"
            failed.ended_at = datetime.now(timezone.utc)
            db.add(ReminderEvent(reminder_id=reminder_id, event="voice_session_failed", detail=type(exc).__name__))
            db.commit()
        # The browser never receives service credentials or a token for an incomplete dispatch.
        raise HTTPException(503, "LiveKit room or agent dispatch failed") from exc


async def close_browser_voice_session(db: Session, session_id: UUID, student_id: UUID) -> dict:
    row = db.scalar(select(VoiceSession).where(VoiceSession.id == session_id, VoiceSession.student_id == student_id))
    if not row:
        raise HTTPException(404, "Voice session not found")
    if row.status not in {"ended", "failed", "closed"} and settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret:
        try:
            async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
                await lk.room.delete_room(api.DeleteRoomRequest(room=row.room_name))
        except Exception:
            pass
    row.status = "closed"
    row.ended_at = datetime.now(timezone.utc)
    if row.reminder_id:
        db.add(ReminderEvent(reminder_id=row.reminder_id, event="voice_session_closed", detail=str(row.id)))
    db.commit()
    return {"session_id": str(row.id), "status": row.status}
