"""Persistent, independently run assistant job worker (safe mock delivery only)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone, time
import json
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.config import get_settings
from backend.app.db.models import (AssistantAccount, AssistantAuditEvent, AssistantCallAttempt,
    AssistantCalendarEvent, AssistantDeadline, AssistantDeadlineCandidate, AssistantDraft,
    AssistantEmailMessage, AssistantJob, AssistantLocalCall, AssistantSettings)
from backend.app.services.assistant_providers import (ProviderFailure, ProviderUnavailable,
    google_ready, twilio_create_call, twilio_destination_allowed, twilio_live_ready)
from backend.app.services.assistant_google import list_calendar_events, sync_gmail


def _quiet_end_utc(now: datetime, settings: AssistantSettings) -> datetime | None:
    if not settings.quiet_start or not settings.quiet_end:
        return None
    zone = ZoneInfo(settings.timezone_name)
    local = now.astimezone(zone)
    start_h, start_m = map(int, settings.quiet_start.split(":"))
    end_h, end_m = map(int, settings.quiet_end.split(":"))
    local_minute = local.hour * 60 + local.minute
    start_minute = start_h * 60 + start_m
    end_minute = end_h * 60 + end_m
    crosses_midnight = start_minute >= end_minute
    inside = (local_minute >= start_minute or local_minute < end_minute) if crosses_midnight else (start_minute <= local_minute < end_minute)
    if not inside:
        return None
    end_date = local.date() + timedelta(days=1) if crosses_midnight and local_minute >= start_minute else local.date()
    end = datetime.combine(end_date, time(end_h, end_m), tzinfo=zone)
    result = end.astimezone(timezone.utc)
    # During the repeated fall-back hour, choose the second occurrence if the first is past.
    if result <= now and end.fold == 0:
        result = end.replace(fold=1).astimezone(timezone.utc)
    if result <= now:
        end = datetime.combine(end_date + timedelta(days=1), time(end_h, end_m), tzinfo=zone)
        result = end.astimezone(timezone.utc)
    return result


def run_due_jobs(db: Session, *, now: datetime | None = None, limit: int = 25,
                 allow_live_operations: bool = False) -> int:
    """Claim persistent work. Tests default to mock-only; production must opt in separately."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    db.execute(
        AssistantDeadline.__table__.update()
        .where(AssistantDeadline.status == "upcoming", AssistantDeadline.due_at < current)
        .values(status="overdue")
    )
    active_calls = db.scalars(select(AssistantLocalCall).where(AssistantLocalCall.status == "answered")).all()
    for local_call in active_calls:
        answered_at = local_call.answered_at
        if answered_at is None:
            continue
        if answered_at.tzinfo is None:
            answered_at = answered_at.replace(tzinfo=timezone.utc)
        if current < answered_at + timedelta(minutes=local_call.max_duration_minutes):
            continue
        local_call.status = "ended"; local_call.ended_at = current
        local_call.mic_authorization_hash = None
        local_call.mic_authorization_expires_at = None
        settings = db.get(AssistantSettings, local_call.student_id)
        try:
            save_transcripts = bool(json.loads(settings.notifications_json or "{}").get("save_call_transcripts", False)) if settings else False
        except (TypeError, ValueError):
            save_transcripts = False
        if not save_transcripts:
            local_call.turns_json = "[]"
        _worker_audit(db, local_call.student_id, "local_call.duration_limit", local_call.id, "ended")
    stale_before = current - timedelta(minutes=5)
    stale_jobs = db.scalars(select(AssistantJob).where(AssistantJob.status == "running",
        AssistantJob.claimed_at.is_not(None), AssistantJob.claimed_at < stale_before)).all()
    for stale in stale_jobs:
        if stale.kind == "reminder":
            attempt = db.scalar(select(AssistantCallAttempt).where(AssistantCallAttempt.job_id == stale.id,
                AssistantCallAttempt.attempt_number == stale.attempts))
            if attempt and not attempt.provider_sid:
                attempt.status = "uncertain"; attempt.failure_code = "worker_interrupted_during_call_request"
                stale.status = "failed"; stale.provider_status = "unknown"; stale.last_error = attempt.failure_code
            else:
                stale.status = "waiting_callback"; stale.provider_status = "accepted"
            stale.claimed_at = None
        elif stale.kind in {"gmail_sync", "calendar_sync"} and stale.attempts < stale.max_attempts:
            stale.status = "retry"; stale.run_at = current + timedelta(seconds=min(3600, 30 * (2 ** max(0, stale.attempts - 1))))
            stale.claimed_at = None; stale.last_error = "worker_interrupted"
        else:
            stale.status = "failed"; stale.claimed_at = None; stale.last_error = "worker_interrupted"
    db.execute(AssistantDraft.__table__.update().where(AssistantDraft.status == "sending",
        AssistantDraft.approved_at < stale_before).values(status="send_uncertain", failure_code="worker_interrupted_during_send"))
    query = select(AssistantJob).where(AssistantJob.status.in_(["queued", "retry"]), AssistantJob.run_at <= current).order_by(AssistantJob.run_at, AssistantJob.id).limit(limit)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    jobs = list(db.scalars(query).all())
    executed = 0
    for job in jobs:
        settings = db.get(AssistantSettings, job.student_id)
        if settings is None or settings.paused:
            continue
        if job.kind in {"gmail_sync", "calendar_sync"}:
            if not allow_live_operations or not google_ready():
                job.status = "failed"; job.provider_status = "unavailable"; job.last_error = "google_live_operations_disabled"
                continue
            account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == job.student_id,
                AssistantAccount.provider == ("gmail" if job.kind == "gmail_sync" else "calendar"), AssistantAccount.status == "connected"))
            if account is None:
                job.status = "canceled"; job.provider_status = "not_connected"; continue
            result = db.execute(AssistantJob.__table__.update().where(AssistantJob.id == job.id,
                AssistantJob.status.in_(["queued", "retry"])).values(status="running", attempts=AssistantJob.attempts + 1, claimed_at=current))
            if not result.rowcount: continue
            try:
                if job.kind == "gmail_sync": sync_gmail(db, job.student_id, account)
                else: list_calendar_events(db, job.student_id, account)
                account.last_error = None
                job.status = "completed"; job.provider_status = "synchronized"; job.last_error = None; job.claimed_at = None
                next_at = current + timedelta(minutes=15)
                db.add(AssistantJob(student_id=job.student_id, kind=job.kind, status="queued", run_at=next_at,
                    idempotency_key=f"{job.kind}:{account.id}:{int(next_at.timestamp() // 900)}", attempts=0, max_attempts=5))
                executed += 1
            except (ProviderFailure, ProviderUnavailable) as exc:
                job.last_error = exc.code if isinstance(exc, ProviderFailure) else "provider_unavailable"
                account.last_error = job.last_error
                if isinstance(exc, ProviderFailure) and exc.code == "google_reauthorization_required":
                    account.status = "reauthorization_required"; job.status = "failed"
                elif job.attempts < job.max_attempts:
                    job.status = "retry"; job.run_at = current + timedelta(seconds=min(3600, 30 * (2 ** max(0, job.attempts - 1))))
                else: job.status = "failed"
                job.claimed_at = None
            continue
        quiet_until = _quiet_end_utc(current, settings) if job.kind == "reminder" else None
        if quiet_until:
            job.run_at = quiet_until
            continue
        if job.kind == "reminder":
            active_call = db.scalar(select(AssistantLocalCall.id).where(
                AssistantLocalCall.student_id == job.student_id,
                AssistantLocalCall.status.in_(["ringing", "answered"]),
            ).limit(1))
            if active_call is not None:
                # Keep due reminders durable, but never ring over an existing call.
                # The worker will retry promptly after the current call ends.
                job.run_at = current + timedelta(seconds=30)
                job.last_error = "deferred_for_active_call"
                continue
        # Conditional state change prevents duplicate execution under concurrent workers.
        result = db.execute(
            AssistantJob.__table__.update()
            .where(AssistantJob.id == job.id, AssistantJob.status.in_(["queued", "retry"]))
            .values(status="running", attempts=AssistantJob.attempts + 1, claimed_at=current)
        )
        if not result.rowcount:
            continue
        db.flush()
        deadline = db.get(AssistantDeadline, job.deadline_id) if job.deadline_id else None
        if job.kind == "reminder" and (
            deadline is None
            or deadline.status not in {"upcoming", "overdue"}
        ):
            job.status = "canceled"
            job.provider_status = "not_attempted"
            job.last_error = "Deadline is no longer active"
            job.claimed_at = None
        else:
            cfg = get_settings()
            try:
                notifications = json.loads(settings.notifications_json or "{}")
            except (TypeError, ValueError):
                notifications = {}
            if job.kind == "reminder" and notifications.get("desktop_call") is True:
                existing_local_call = db.scalar(select(AssistantLocalCall).where(AssistantLocalCall.job_id == job.id))
                if existing_local_call is None:
                    local_call = AssistantLocalCall(student_id=job.student_id, deadline_id=deadline.id,
                        job_id=job.id, status="ringing", language=settings.preferred_language,
                        max_duration_minutes=settings.max_call_duration_minutes)
                    db.add(local_call)
                    db.flush()
                    _worker_audit(db, job.student_id, "local_call.ringing", local_call.id, "desktop_pending",
                                  {"deadline_id": deadline.id})
                job.status = "completed"; job.provider_status = "desktop_pending"; job.last_error = None
                job.claimed_at = None
                executed += 1
                continue
            live = (allow_live_operations and cfg.app_env == "production" and cfg.assistant_live_operations_enabled
                    and twilio_live_ready(cfg) and settings.phone_verified and settings.call_consent_at
                    and settings.reminder_phone)
            if live and not twilio_destination_allowed(settings.reminder_phone, cfg):
                job.status = "failed"; job.provider_status = "destination_blocked"; job.last_error = "destination_not_allowlisted"; job.claimed_at = None
                _worker_audit(db, job.student_id, "call.blocked", job.id, "destination_not_allowlisted")
                continue
            if live and job.kind == "reminder":
                daily_count = db.scalar(select(func.count(AssistantCallAttempt.id)).where(
                    AssistantCallAttempt.student_id == job.student_id,
                    AssistantCallAttempt.created_at >= current - timedelta(hours=24))) or 0
                if daily_count >= cfg.assistant_max_calls_per_day:
                    job.status = "failed"; job.provider_status = "rate_limited"; job.last_error = "daily_call_limit"; job.claimed_at = None
                    continue
                db.refresh(job)
                attempt_no = job.attempts
                attempt = AssistantCallAttempt(student_id=job.student_id, job_id=job.id, attempt_number=attempt_no,
                    idempotency_key=f"{job.id}:call-attempt:{attempt_no}", destination=settings.reminder_phone,
                    status="requesting", provider_status=None)
                db.add(attempt); db.flush()
                zone = ZoneInfo(deadline.timezone_name)
                local_due = deadline.due_at.astimezone(zone).strftime("%A, %B %d at %I:%M %p")
                spoken = f"Reminder: {deadline.title}. It is due {local_due}."
                language = settings.preferred_language
                db.commit()  # Persist attempt before crossing the non-idempotent provider boundary.
                try:
                    result = twilio_create_call(settings.reminder_phone, spoken, language)
                    attempt.provider_sid = result["sid"]; attempt.status = result["status"]
                    attempt.provider_status = result["status"]; attempt.updated_at = current
                    job.status = "waiting_callback"; job.provider_status = result["status"]; job.last_error = None
                    job.claimed_at = None
                    _worker_audit(db, job.student_id, "call.created", attempt.id, "provider_accepted")
                    db.commit(); executed += 1
                except ProviderFailure as exc:
                    attempt.failure_code = exc.code; attempt.status = "failed" if exc.retryable else "uncertain"
                    attempt.provider_status = "unknown" if not exc.retryable else "rejected"
                    job.last_error = exc.code
                    job.claimed_at = None
                    if exc.retryable and job.attempts < job.max_attempts:
                        job.status = "retry"; job.run_at = current + timedelta(seconds=min(3600, 30 * (2 ** max(0, job.attempts - 1))))
                    else: job.status = "failed"
                    _worker_audit(db, job.student_id, "call.failed", attempt.id, attempt.status, {"code": exc.code})
                    db.commit()
            else:
                # The mock outcome is explicit and cannot be mistaken for a real call.
                job.status = "completed"; job.provider_status = "mocked"; job.last_error = None
                job.claimed_at = None
                executed += 1
    # Expire personal assistant records according to each owner's retention setting.
    for pref in db.scalars(select(AssistantSettings).where(AssistantSettings.retention_days > 0)).all():
        cutoff = current - timedelta(days=pref.retention_days)
        db.execute(AssistantEmailMessage.__table__.delete().where(AssistantEmailMessage.student_id == pref.student_id,
            AssistantEmailMessage.processed_at < cutoff))
        db.execute(AssistantDeadlineCandidate.__table__.delete().where(AssistantDeadlineCandidate.student_id == pref.student_id,
            AssistantDeadlineCandidate.created_at < cutoff))
        db.execute(AssistantDraft.__table__.delete().where(AssistantDraft.student_id == pref.student_id,
            AssistantDraft.created_at < cutoff, AssistantDraft.status.not_in(["sending", "send_uncertain"])))
        db.execute(AssistantCallAttempt.__table__.delete().where(AssistantCallAttempt.student_id == pref.student_id,
            AssistantCallAttempt.created_at < cutoff))
        db.execute(AssistantCalendarEvent.__table__.delete().where(AssistantCalendarEvent.student_id == pref.student_id,
            AssistantCalendarEvent.updated_at < cutoff))
        db.execute(AssistantAuditEvent.__table__.delete().where(AssistantAuditEvent.student_id == pref.student_id,
            AssistantAuditEvent.created_at < cutoff))
        db.execute(AssistantJob.__table__.delete().where(AssistantJob.student_id == pref.student_id,
            AssistantJob.created_at < cutoff, AssistantJob.status.in_(["completed", "failed", "canceled"])))
        db.execute(AssistantDeadline.__table__.delete().where(AssistantDeadline.student_id == pref.student_id,
            AssistantDeadline.created_at < cutoff, AssistantDeadline.status.in_(["completed", "canceled"])))
    db.commit()
    return executed


def _worker_audit(db: Session, owner: str, action: str, target_id: str, outcome: str, details=None):
    import json
    from backend.app.db.models import AssistantAuditEvent
    db.add(AssistantAuditEvent(student_id=owner, action=action, target_type="call", target_id=target_id,
        outcome=outcome, details_json=json.dumps(details or {}, separators=(",", ":"))))
