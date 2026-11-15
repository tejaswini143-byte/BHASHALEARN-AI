"""Authenticated LiveKit rooms for the production BHASHALEARN assistant."""
from datetime import datetime, timedelta, timezone
import json
from sqlalchemy import select
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException
from livekit import api

from backend.app.config import get_settings
from backend.app.db.models import (AssistantAuditEvent, AssistantCallAttempt, AssistantDeadline, AssistantJob,
                                  AssistantLiveKitSession, AssistantSettings, new_id)


def _notifications(row: AssistantSettings | None) -> dict:
    try:
        value = json.loads(row.notifications_json or "{}") if row else {}
    except (TypeError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def blockers() -> list[str]:
    config = get_settings()
    return [name for name, value in (
        ("BHASHALEARN_LIVEKIT_URL", config.livekit_url),
        ("BHASHALEARN_LIVEKIT_API_KEY", config.livekit_api_key),
        ("BHASHALEARN_LIVEKIT_API_SECRET", config.livekit_api_secret),
        ("BHASHALEARN_GEMINI_API_KEY", config.gemini_api_key),
        ("BHASHALEARN_GNANI_API_KEY", config.gnani_api_key),
    ) if not value.strip()]


async def create_session(db: Session, student_id: str, deadline_id: str, language: str) -> dict:
    config = get_settings()
    missing = blockers()
    if missing:
        raise HTTPException(503, {"message": "LiveKit voice is not configured", "missing": missing})
    deadline = db.scalar(select(AssistantDeadline).where(
        AssistantDeadline.id == deadline_id, AssistantDeadline.student_id == student_id))
    if deadline is None:
        raise HTTPException(404, "Deadline not found")
    if deadline.status not in {"upcoming", "overdue"}:
        raise HTTPException(409, "Deadline is not active")
    preferences = db.get(AssistantSettings, student_id)
    if preferences and (preferences.paused or not _notifications(preferences).get("desktop_call", False)):
        raise HTTPException(403, "In-browser reminder calls are disabled in assistant preferences")
    session_id = new_id()
    room_name = f"bhashalearn-deadline-{session_id.replace('-', '')}"
    row = AssistantLiveKitSession(id=session_id, student_id=student_id, deadline_id=deadline_id,
                                  room_name=room_name, language=language, status="creating")
    db.add(row)
    db.commit()
    try:
        async with api.LiveKitAPI(config.livekit_url, config.livekit_api_key, config.livekit_api_secret) as lk:
            await lk.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=60, max_participants=2))
            await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=config.livekit_agent_name, room=room_name,
                metadata=json.dumps({"assistant_livekit_session_id": session_id}),
            ))
        token = (api.AccessToken(config.livekit_api_key, config.livekit_api_secret)
                 .with_identity(f"student-{student_id}").with_name("BHASHALEARN student")
                 .with_ttl(timedelta(minutes=10))
                 .with_grants(api.VideoGrants(room_join=True, room=room_name, can_publish=True,
                                              can_subscribe=True, can_publish_data=True)).to_jwt())
        row.status = "dispatched"
        db.commit()
        return {"session_id": session_id, "room_name": room_name, "server_url": config.livekit_url,
                "participant_token": token, "expires_in_seconds": 600, "status": row.status,
                "provider_mode": "turn-based-rest"}
    except Exception as exc:
        db.rollback()
        failed = db.get(AssistantLiveKitSession, session_id)
        if failed:
            failed.status = "failed"
            failed.ended_at = datetime.now(timezone.utc)
            db.commit()
        raise HTTPException(503, "LiveKit room creation or agent dispatch failed") from exc


async def close_session(db: Session, student_id: str, session_id: str) -> dict:
    config = get_settings()
    row = db.scalar(select(AssistantLiveKitSession).where(
        AssistantLiveKitSession.id == session_id,
        AssistantLiveKitSession.student_id == student_id,
    ))
    if row is None:
        raise HTTPException(404, "LiveKit session not found")
    if row.status not in {"closed", "failed", "ended"} and config.livekit_url and config.livekit_api_key and config.livekit_api_secret:
        try:
            async with api.LiveKitAPI(config.livekit_url, config.livekit_api_key, config.livekit_api_secret) as lk:
                await lk.room.delete_room(api.DeleteRoomRequest(room=row.room_name))
        except Exception:
            pass
    row.status = "closed"
    row.ended_at = datetime.now(timezone.utc)
    db.commit()
    return {"session_id": row.id, "status": row.status}


def sip_blockers(preferences: AssistantSettings | None) -> list[str]:
    config = get_settings()
    missing = []
    for name, value in (("BHASHALEARN_LIVEKIT_URL", config.livekit_url),
                        ("BHASHALEARN_LIVEKIT_API_KEY", config.livekit_api_key),
                        ("BHASHALEARN_LIVEKIT_API_SECRET", config.livekit_api_secret)):
        if not value: missing.append(name)
    if not config.livekit_calls_enabled: missing.append("BHASHALEARN_LIVEKIT_CALLS_ENABLED=true")
    if not config.livekit_sip_outbound_trunk_id: missing.append("BHASHALEARN_LIVEKIT_SIP_OUTBOUND_TRUNK_ID")
    if not config.livekit_sip_caller_id: missing.append("BHASHALEARN_LIVEKIT_SIP_CALLER_ID (approved caller ID)")
    if not preferences or not preferences.call_consent_at: missing.append("active student call consent")
    if not preferences or not preferences.reminder_phone or not preferences.phone_verified:
        missing.append("verified student phone number")
    allowed = {number.strip() for number in config.livekit_verified_test_numbers.split(",") if number.strip()}
    if not allowed: missing.append("BHASHALEARN_LIVEKIT_VERIFIED_TEST_NUMBERS allowlist")
    elif preferences and preferences.reminder_phone not in allowed: missing.append("phone number on verified test allowlist")
    return missing


async def start_sip_call(db: Session, student_id: str, deadline_id: str, confirmed: bool) -> dict:
    config = get_settings()
    if not confirmed:
        raise HTTPException(400, "Explicit call confirmation is required")
    deadline = db.scalar(select(AssistantDeadline).where(
        AssistantDeadline.id == deadline_id, AssistantDeadline.student_id == student_id))
    if deadline is None: raise HTTPException(404, "Deadline not found")
    if deadline.status not in {"upcoming", "overdue"}: raise HTTPException(409, "Deadline is not active")
    prefs = db.get(AssistantSettings, student_id)
    missing = sip_blockers(prefs)
    if missing: raise HTTPException(503, {"message": "LiveKit SIP calls are blocked", "missing": missing})
    if prefs.paused: raise HTTPException(403, "Reminder automation is paused")
    now = datetime.now(timezone.utc)
    try: zone = ZoneInfo(prefs.timezone_name)
    except (ZoneInfoNotFoundError, ValueError): raise HTTPException(422, "Student timezone is invalid")
    hour = datetime.now(zone).hour
    if not config.livekit_call_start_hour <= hour < config.livekit_call_end_hour:
        raise HTTPException(403, "Calls are outside the configured student calling hours")
    recent = db.scalar(select(func.count(AssistantCallAttempt.id)).where(
        AssistantCallAttempt.student_id == student_id,
        AssistantCallAttempt.created_at >= now - timedelta(days=1),
        AssistantCallAttempt.status.not_in(["failed", "canceled", "rejected"]))) or 0
    if recent >= config.livekit_max_calls_per_day: raise HTTPException(429, "Daily call limit reached")
    key = f"livekit-sip:{deadline.id}:{now.astimezone(zone).date().isoformat()}"
    previous = db.scalar(select(AssistantCallAttempt).where(
        AssistantCallAttempt.student_id == student_id, AssistantCallAttempt.idempotency_key == key))
    if previous: return {"call_id": previous.id, "status": previous.status, "duplicate": True}
    call_id, session_id, job_id = new_id(), new_id(), new_id()
    room_name = f"bhashalearn-sip-{session_id.replace('-', '')}"
    identity = f"phone-{call_id.replace('-', '')}"
    row = AssistantLiveKitSession(id=session_id, student_id=student_id, deadline_id=deadline.id,
                                  room_name=room_name, language=prefs.preferred_language, status="creating")
    job = AssistantJob(id=job_id, student_id=student_id, deadline_id=deadline.id, kind="phone_call",
                       status="running", run_at=now, idempotency_key=f"{key}:job", attempts=1, max_attempts=1)
    attempt = AssistantCallAttempt(id=call_id, student_id=student_id, job_id=job_id, attempt_number=1,
        idempotency_key=key, destination=prefs.reminder_phone, status="dispatching",
        livekit_session_id=session_id, participant_identity=identity)
    db.add_all([row, job, attempt])
    try: db.commit()
    except IntegrityError:
        db.rollback()
        previous = db.scalar(select(AssistantCallAttempt).where(
            AssistantCallAttempt.student_id == student_id, AssistantCallAttempt.idempotency_key == key))
        if previous: return {"call_id": previous.id, "status": previous.status, "duplicate": True}
        raise
    try:
        async with api.LiveKitAPI(config.livekit_url, config.livekit_api_key, config.livekit_api_secret) as lk:
            await lk.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=60, max_participants=3))
            await lk.agent_dispatch.create_dispatch(api.CreateAgentDispatchRequest(
                agent_name=config.livekit_agent_name, room=room_name,
                metadata=json.dumps({"assistant_livekit_session_id": session_id})))
            await lk.sip.create_sip_participant(api.CreateSIPParticipantRequest(
                sip_trunk_id=config.livekit_sip_outbound_trunk_id, sip_call_to=prefs.reminder_phone,
                sip_number=config.livekit_sip_caller_id, room_name=room_name,
                participant_identity=identity, participant_name="BHASHALEARN deadline reminder"))
        attempt.status = "ringing"; row.status = "dispatched"; job.status = "completed"
        db.add(AssistantAuditEvent(student_id=student_id, action="assistant.sip_call.dispatched",
            target_type="assistant_deadline", target_id=deadline.id, outcome="ringing"))
        db.commit()
        return {"call_id": call_id, "status": "ringing", "duplicate": False}
    except Exception as exc:
        db.rollback()
        attempt = db.get(AssistantCallAttempt, call_id); row = db.get(AssistantLiveKitSession, session_id)
        if attempt: attempt.status = "failed"; attempt.failure_code = type(exc).__name__
        if row: row.status = "failed"; row.ended_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(503, "LiveKit SIP dispatch failed") from exc
