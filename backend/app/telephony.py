"""Guarded LiveKit SIP dispatch. Live calls require explicit authenticated action."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from livekit import api

from .models import CallAttempt, Deadline, Reminder, ReminderEvent, ReminderPreference, VoiceSession
from .settings import settings


def classify_sip_failure(error: Exception) -> str:
    code = getattr(error, "sip_status_code", None)
    reason = (getattr(error, "sip_status", None) or str(error)).casefold()
    if code == 486 or "busy" in reason:
        return "busy"
    if code in {403, 404, 407, 488, 603} or "reject" in reason or "forbidden" in reason:
        return "rejected"
    if code in {408, 480, 504} or "timeout" in reason or "no answer" in reason:
        return "no_answer"
    return "failed"


def telephony_blockers(preferences, verified_test_numbers: set[str] | None = None) -> list[str]:
    missing = []
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        missing.append("LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
    if not settings.sip_outbound_trunk_id:
        missing.append("SIP_OUTBOUND_TRUNK_ID")
    if not settings.sip_caller_id:
        missing.append("SIP_CALLER_ID (approved caller identity)")
    if not preferences or not preferences.call_enabled or not preferences.call_consent_at or preferences.opted_out_at:
        missing.append("active student call consent")
    if not preferences or not preferences.phone_e164 or not preferences.phone_verified_at:
        missing.append("verified student phone number")
    if not settings.allow_test_calls:
        missing.append("ALLOW_TEST_CALLS=true")
    allowlist = verified_test_numbers if verified_test_numbers is not None else {
        number.strip() for number in settings.verified_test_numbers.split(",") if number.strip()
    }
    if not allowlist:
        missing.append("VERIFIED_TEST_NUMBERS allowlist")
    elif preferences and preferences.phone_e164 not in allowlist:
        missing.append("phone number allowlisted as a verified test number")
    return missing


async def start_outbound_reminder_call(db: Session, student_id, reminder_id):
    """Create one consented, test-allowlisted SIP call and retain its audit record."""
    reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.student_id == student_id))
    if not reminder:
        raise HTTPException(404, "Reminder not found")
    prefs = db.get(ReminderPreference, student_id)
    blockers = telephony_blockers(prefs)
    if blockers:
        raise HTTPException(503, {"message": "Outbound calls are disabled", "missing": blockers})
    deadline = db.get(Deadline, reminder.deadline_id)
    if not deadline or deadline.cancelled_at or deadline.completed_at:
        raise HTTPException(409, "This deadline is no longer active")
    try:
        zone = ZoneInfo(prefs.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Student timezone is invalid")
    local_hour = datetime.now(zone).hour
    if not settings.call_start_hour <= local_hour < settings.call_end_hour:
        raise HTTPException(403, "Calls are only allowed during configured calling hours")

    idempotency_key = f"reminder-call:{reminder.id}:{reminder.scheduled_at.isoformat()}"
    existing = db.scalar(select(CallAttempt).where(CallAttempt.idempotency_key == idempotency_key))
    if existing:
        return {"call_id": str(existing.id), "status": existing.status, "duplicate": True}
    now = datetime.now(timezone.utc)
    recent_count = db.scalar(select(func.count(CallAttempt.id)).where(
        CallAttempt.student_id == student_id,
        CallAttempt.created_at >= now - timedelta(days=1),
        CallAttempt.status.not_in(["failed", "cancelled"]),
    )) or 0
    if recent_count >= settings.max_calls_per_day:
        raise HTTPException(429, "Daily reminder call limit reached")

    session_id, call_id = uuid4(), uuid4()
    room_name = f"deadline-call-{session_id.hex}"
    identity = f"phone-{call_id.hex}"
    voice_session = VoiceSession(id=session_id, student_id=student_id, reminder_id=reminder.id,
                                 room_name=room_name, language=prefs.language, status="creating")
    attempt = CallAttempt(id=call_id, student_id=student_id, reminder_id=reminder.id,
                          voice_session_id=session_id, phone_e164=prefs.phone_e164,
                          room_name=room_name, participant_identity=identity,
                          status="dispatching", idempotency_key=idempotency_key)
    db.add_all([voice_session, attempt])
    db.add(ReminderEvent(reminder_id=reminder.id, event="outbound_call_requested", detail=str(call_id)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = db.scalar(select(CallAttempt).where(CallAttempt.idempotency_key == idempotency_key))
        if winner:
            return {"call_id": str(winner.id), "status": winner.status, "duplicate": True}
        raise
    try:
        async with api.LiveKitAPI(settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret) as lk:
            await lk.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=60, max_participants=3))
            await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=settings.livekit_agent_name,
                room=room_name,
                metadata=__import__("json").dumps({"voice_session_id": str(session_id), "call_id": str(call_id)}),
            ))
            await lk.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                sip_trunk_id=settings.sip_outbound_trunk_id,
                sip_call_to=prefs.phone_e164,
                sip_number=settings.sip_caller_id,
                room_name=room_name,
                participant_identity=identity,
                participant_name="BHASHALEARN deadline reminder",
            ))
        attempt.status = "ringing"
        db.add(ReminderEvent(reminder_id=reminder.id, event="outbound_call_ringing", detail=str(call_id)))
        db.commit()
        return {"call_id": str(call_id), "status": attempt.status, "duplicate": False}
    except Exception as exc:
        db.rollback()
        failure_status = classify_sip_failure(exc)
        attempt = db.get(CallAttempt, call_id)
        voice_session = db.get(VoiceSession, session_id)
        if attempt:
            attempt.status = failure_status
            sip_code = getattr(exc, "sip_status_code", None)
            attempt.failure_detail = f"{type(exc).__name__}" + (f": SIP {sip_code}" if sip_code else "")
        if voice_session:
            voice_session.status = "failed"
            voice_session.ended_at = datetime.now(timezone.utc)
        db.add(ReminderEvent(reminder_id=reminder.id, event=f"outbound_call_{failure_status}", detail=type(exc).__name__))
        db.commit()
        raise HTTPException(503, "LiveKit SIP call dispatch failed") from exc

