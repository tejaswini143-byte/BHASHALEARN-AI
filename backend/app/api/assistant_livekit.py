"""LiveKit browser reminder sessions mounted inside the production API."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.config import get_settings
from backend.app.db.models import AssistantLiveKitSession, Student
from backend.app.db.session import get_db
from backend.app.services.assistant_livekit import blockers, close_session, create_session, start_sip_call
from livekit import api as livekit_api
from backend.app.db.models import AssistantCallAttempt

router = APIRouter(prefix="/assistant", tags=["deadline reminders - LiveKit"])


class VoiceSessionRequest(BaseModel):
    language: str = Field(default="mixed", pattern="^(en|te|mixed|en-IN|te-IN)$")


class SIPCallRequest(BaseModel):
    explicit_confirmation: bool


@router.get("/livekit/status")
def livekit_status(student: Student = Depends(current_student)):
    missing = blockers()
    return {"available": not missing, "provider_mode": "turn-based-rest" if not missing else "unconfigured",
            "missing": missing}


@router.post("/deadlines/{deadline_id}/livekit-session")
async def start_deadline_voice(deadline_id: str, body: VoiceSessionRequest,
                              student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return await create_session(db, student.id, deadline_id, body.language)


@router.post("/deadlines/{deadline_id}/sip-call")
async def start_deadline_sip_call(deadline_id: str, body: SIPCallRequest,
                                  student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return await start_sip_call(db, student.id, deadline_id, body.explicit_confirmation)


@router.post("/livekit-sessions/{session_id}/close")
async def end_deadline_voice(session_id: str, student: Student = Depends(current_student),
                             db: Session = Depends(get_db)):
    return await close_session(db, student.id, session_id)


@router.get("/livekit-sessions")
def list_deadline_voice_sessions(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(AssistantLiveKitSession).where(
        AssistantLiveKitSession.student_id == student.id
    ).order_by(AssistantLiveKitSession.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "deadline_id": row.deadline_id, "status": row.status,
             "language": row.language, "created_at": row.created_at, "ended_at": row.ended_at} for row in rows]


@router.post("/livekit/webhook")
async def livekit_webhook(request: Request, authorization: str | None = Header(default=None),
                          db: Session = Depends(get_db)):
    config = get_settings()
    if not authorization or not config.livekit_api_key or not config.livekit_api_secret:
        raise HTTPException(401, "Signed LiveKit webhook credentials are required")
    try:
        receiver = livekit_api.WebhookReceiver(livekit_api.TokenVerifier(config.livekit_api_key, config.livekit_api_secret))
        event = receiver.receive((await request.body()).decode("utf-8"), authorization)
    except Exception as exc:
        raise HTTPException(401, "Invalid LiveKit webhook signature") from exc
    identity = event.participant.identity if event.HasField("participant") else None
    if not identity: return {"accepted": True, "matched": False}
    attempt = db.scalar(select(AssistantCallAttempt).where(AssistantCallAttempt.participant_identity == identity))
    if not attempt: return {"accepted": True, "matched": False}
    if event.event == "participant_joined" and attempt.status == "ringing": attempt.status = "answered"
    elif event.event == "participant_left":
        attempt.status = "ended" if attempt.status == "answered" else "no_answer"
    if event.event in {"participant_left", "room_finished"}:
        attempt.updated_at = datetime.now(timezone.utc)
        session = db.get(AssistantLiveKitSession, attempt.livekit_session_id) if attempt.livekit_session_id else None
        if session: session.status = "ended"; session.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"accepted": True, "matched": True, "status": attempt.status}
