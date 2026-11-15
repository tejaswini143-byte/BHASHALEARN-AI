import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Deadline, Reminder, ReminderEvent, ReminderPreference
from .schemas import DeadlineIn, DeadlineOut, PreferencesIn, ReminderAction, ReminderOut
from .settings import settings

router = APIRouter(prefix="/api", tags=["deadlines"])
bearer = HTTPBearer(auto_error=False)


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def student_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(db_session)) -> uuid.UUID:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in required")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])
        sid = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid student identity") from exc
    from .models import Student
    if db.get(Student, sid) is None:
        raise HTTPException(401, "Student account not found")
    return sid


def owned_deadline(db: Session, did: uuid.UUID, sid: uuid.UUID) -> Deadline:
    item = db.scalar(select(Deadline).where(Deadline.id == did, Deadline.student_id == sid))
    if not item:
        raise HTTPException(404, "Deadline not found")
    return item


def schedule(db: Session, deadline: Deadline, sid: uuid.UUID) -> Reminder:
    if deadline.delivery_mode == "call":
        prefs = db.get(ReminderPreference, sid)
        if not prefs or not prefs.call_enabled or not prefs.call_consent_at or prefs.opted_out_at:
            raise HTTPException(403, "Active call consent is required for phone reminders")
    when = deadline.due_at - timedelta(minutes=deadline.reminder_minutes_before)
    if when < datetime.now(timezone.utc):
        when = datetime.now(timezone.utc) + timedelta(seconds=5)
    channel = deadline.delivery_mode
    key = f"deadline:{deadline.id}:at:{when.isoformat()}:{channel}"
    existing = db.scalar(select(Reminder).where(Reminder.idempotency_key == key))
    if existing:
        if existing.status in {"cancelled", "failed"}:
            existing.status = "scheduled"
            existing.scheduled_at = when
            existing.attempts = 0
        return existing
    row = Reminder(deadline_id=deadline.id, student_id=sid, scheduled_at=when,
                   channel=channel, status="scheduled", idempotency_key=key)
    db.add(row)
    db.flush()
    db.add(ReminderEvent(reminder_id=row.id, event="scheduled"))
    return row


@router.post("/deadlines", response_model=DeadlineOut, status_code=201)
def create_deadline(body: DeadlineIn, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    item = Deadline(student_id=sid, **body.model_dump())
    db.add(item)
    db.flush()
    schedule(db, item, sid)
    db.commit()
    db.refresh(item)
    return item


@router.get("/deadlines", response_model=list[DeadlineOut])
def list_deadlines(sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    return list(db.scalars(select(Deadline).where(Deadline.student_id == sid, Deadline.cancelled_at.is_(None)).order_by(Deadline.due_at.desc())))


@router.patch("/deadlines/{did}", response_model=DeadlineOut)
def edit_deadline(did: uuid.UUID, body: DeadlineIn, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    item = owned_deadline(db, did, sid)
    for key, value in body.model_dump().items():
        setattr(item, key, value)
    for reminder in item.reminders:
        if reminder.status == "scheduled":
            reminder.status = "cancelled"
            db.add(ReminderEvent(reminder_id=reminder.id, event="rescheduled"))
    schedule(db, item, sid)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/deadlines/{did}", status_code=204)
def delete_deadline(did: uuid.UUID, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    item = owned_deadline(db, did, sid)
    item.cancelled_at = datetime.now(timezone.utc)
    for reminder in item.reminders:
        if reminder.status == "scheduled":
            reminder.status = "cancelled"
    db.commit()


@router.get("/reminders", response_model=list[ReminderOut])
def list_reminders(sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    return list(db.scalars(select(Reminder).where(Reminder.student_id == sid).order_by(Reminder.scheduled_at.desc()).limit(200)))


@router.post("/reminders/{rid}/action", response_model=ReminderOut)
def action(rid: uuid.UUID, body: ReminderAction, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    row = db.scalar(select(Reminder).where(Reminder.id == rid, Reminder.student_id == sid))
    if not row:
        raise HTTPException(404, "Reminder not found")
    now = datetime.now(timezone.utc)
    if body.action in {"snooze", "reschedule"} and (body.until is None or body.until <= now):
        raise HTTPException(422, "A future 'until' time is required")
    if body.action == "snooze":
        row.status = "scheduled"
        row.snoozed_until = body.until
        row.scheduled_at = body.until
    elif body.action == "reschedule":
        row.status = "scheduled"
        row.scheduled_at = body.until
        row.snoozed_until = None
    elif body.action == "cancel":
        row.status = "cancelled"
    else:
        row.status = "completed" if body.action == "completed" else "acknowledged"
        if body.action == "completed":
            row.deadline.completed_at = now
    db.add(ReminderEvent(reminder_id=row.id, event=body.action, detail=body.detail))
    db.commit()
    db.refresh(row)
    return row


@router.get("/reminders/{rid}/history")
def history(rid: uuid.UUID, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    row = db.scalar(select(Reminder).where(Reminder.id == rid, Reminder.student_id == sid))
    if not row:
        raise HTTPException(404, "Reminder not found")
    return list(db.scalars(select(ReminderEvent).where(ReminderEvent.reminder_id == rid).order_by(ReminderEvent.occurred_at)))


@router.put("/preferences")
def preferences(body: PreferencesIn, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    row = db.get(ReminderPreference, sid)
    if row is None:
        row = ReminderPreference(student_id=sid)
        db.add(row)
    row.timezone, row.language = body.timezone, body.language
    row.reminders_enabled = body.reminders_enabled
    row.voice_enabled, row.call_enabled = body.voice_enabled, body.call_enabled
    row.call_consent_at = datetime.now(timezone.utc) if body.consent else None
    if not body.consent:
        row.call_enabled = False
        row.opted_out_at = datetime.now(timezone.utc)
    else:
        row.opted_out_at = None
    db.commit()
    return {"timezone": row.timezone, "language": row.language, "reminders_enabled": row.reminders_enabled, "voice_enabled": row.voice_enabled,
            "call_enabled": row.call_enabled, "consent": row.call_consent_at is not None}


@router.post("/reminders/{rid}/voice-turn")
def voice_turn(rid: uuid.UUID, body: dict, sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    transcript = body.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip() or len(transcript) > 1000:
        raise HTTPException(422, "Provide a transcript of 1 to 1000 characters")
    row = db.scalar(select(Reminder).where(Reminder.id == rid, Reminder.student_id == sid))
    if not row:
        raise HTTPException(404, "Reminder not found")
    prefs = db.get(ReminderPreference, sid)
    language = prefs.language if prefs else "te-IN"
    if settings.gemini_api_key:
        from .conversation import interpret_turn
        try:
            intent, reply, minutes = interpret_turn(transcript.strip(), row.deadline.title, language)
        except Exception as exc:
            raise HTTPException(503, "The conversation service is temporarily unavailable") from exc
    else:
        from .voice import response_for
        intent, reply, _ = response_for(transcript.strip(), language, row.deadline.title)
        minutes = 30 if intent == "snooze" else None
    if intent == "completed":
        row.status = "completed"
        row.deadline.completed_at = datetime.now(timezone.utc)
    elif intent == "acknowledged":
        row.status = "acknowledged"
    elif intent == "snooze":
        if not minutes:
            return {"intent": "clarify", "reply": "How many minutes should I wait?", "status": row.status}
        row.snoozed_until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        row.scheduled_at = row.snoozed_until
        row.status = "scheduled"
    elif intent == "reschedule":
        try:
            zone = ZoneInfo(prefs.timezone if prefs else row.deadline.timezone)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("Asia/Kolkata")
        local_now = datetime.now(zone)
        row.scheduled_at = (local_now + timedelta(days=1)).astimezone(timezone.utc)
        row.status = "scheduled"
        row.snoozed_until = None
    db.add(ReminderEvent(reminder_id=row.id, event=intent, detail=transcript.strip()[:500]))
    db.commit()
    return {"intent": intent, "reply": reply, "status": row.status}


@router.get("/preferences")
def get_preferences(sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    row = db.get(ReminderPreference, sid)
    if not row:
        return {"timezone": "Asia/Kolkata", "language": "te-IN", "reminders_enabled": True, "voice_enabled": True, "call_enabled": False, "consent": False}
    return {"timezone": row.timezone, "language": row.language, "reminders_enabled": row.reminders_enabled, "voice_enabled": row.voice_enabled,
            "call_enabled": row.call_enabled, "consent": row.call_consent_at is not None}


@router.get("/telephony/status")
def get_telephony_status(sid: uuid.UUID = Depends(student_id), db: Session = Depends(db_session)):
    from .telephony import telephony_blockers
    prefs = db.get(ReminderPreference, sid)
    blockers = telephony_blockers(prefs)
    return {"enabled": False, "status": "blocked" if blockers else "configured", "blockers": blockers,
            "note": "No outbound call is started by this endpoint."}

