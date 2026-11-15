from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .api import db_session, student_id
from .db import SessionLocal
from .livekit_voice import close_browser_voice_session, create_browser_voice_session, livekit_blockers
from .models import CallAttempt, ReminderEvent, VoiceSession
from .schemas import VoiceSessionIn
from .settings import settings
from livekit import api

router = APIRouter(prefix="/api", tags=["LiveKit voice sessions"])


@router.get("/voice/status")
def voice_status():
    blockers = livekit_blockers()
    return {"available": not blockers, "provider_mode": "turn-based-rest" if not blockers else "unconfigured", "blockers": blockers}


@router.post("/reminders/{reminder_id}/voice-session")
async def start_voice_session(reminder_id: UUID, body: VoiceSessionIn,
                              sid: UUID = Depends(student_id), db: Session = Depends(db_session)):
    return await create_browser_voice_session(db, sid, reminder_id, body.language)


@router.post("/voice/sessions/{session_id}/close")
async def close_voice_session(session_id: UUID, sid: UUID = Depends(student_id), db: Session = Depends(db_session)):
    return await close_browser_voice_session(db, session_id, sid)


@router.get("/voice/sessions")
def list_voice_sessions(sid: UUID = Depends(student_id), db: Session = Depends(db_session)):
    rows = db.scalars(select(VoiceSession).where(VoiceSession.student_id == sid).order_by(VoiceSession.created_at.desc()).limit(100))
    return [{"id": str(row.id), "reminder_id": str(row.reminder_id) if row.reminder_id else None,
             "status": row.status, "language": row.language, "created_at": row.created_at, "ended_at": row.ended_at}
            for row in rows]


@router.post("/reminders/{reminder_id}/call")
async def dispatch_outbound_call(reminder_id: UUID, sid: UUID = Depends(student_id), db: Session = Depends(db_session)):
    """Explicit authenticated call action; never invoked by the reminder poller."""
    from .telephony import start_outbound_reminder_call
    return await start_outbound_reminder_call(db, sid, reminder_id)


@router.get("/calls")
def list_calls(sid: UUID = Depends(student_id), db: Session = Depends(db_session)):
    rows = db.scalars(select(CallAttempt).where(CallAttempt.student_id == sid).order_by(CallAttempt.created_at.desc()).limit(100))
    return [{"id": str(row.id), "reminder_id": str(row.reminder_id), "status": row.status,
             "created_at": row.created_at, "ended_at": row.ended_at, "failure": row.failure_detail}
            for row in rows]


@router.post("/telephony/webhook")
async def telephony_webhook(request: Request, authorization: str | None = Header(default=None)):
    """Verify the LiveKit webhook signature before reconciling SIP participant lifecycle events."""
    if not settings.livekit_api_key or not settings.livekit_api_secret or not authorization:
        raise HTTPException(401, "Signed LiveKit webhook credentials are required")
    body = (await request.body()).decode("utf-8")
    try:
        receiver = api.WebhookReceiver(api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret))
        event = receiver.receive(body, authorization)
    except Exception as exc:
        raise HTTPException(401, "Invalid LiveKit webhook signature or payload") from exc
    room_name = event.room.name if event.HasField("room") else None
    identity = event.participant.identity if event.HasField("participant") else None
    with SessionLocal() as db:
        query = select(CallAttempt)
        if identity:
            query = query.where(CallAttempt.participant_identity == identity)
        elif room_name:
            query = query.where(CallAttempt.room_name == room_name)
        else:
            return {"accepted": True, "matched": False}
        call = db.scalar(query)
        if not call:
            return {"accepted": True, "matched": False}
        event_type = event.event
        if event_type == "participant_joined" and call.status == "ringing":
            call.status = "answered"
        elif event_type == "participant_left":
            call.status = "ended" if call.status == "answered" else "no_answer"
            call.ended_at = datetime.now(timezone.utc)
        elif event_type == "room_finished":
            call.status = "ended" if call.status == "answered" else "no_answer"
            call.ended_at = datetime.now(timezone.utc)
        db.add(ReminderEvent(reminder_id=call.reminder_id, event=f"call_{call.status}", detail=str(call.id)))
        db.commit()
        return {"accepted": True, "matched": True, "status": call.status}
