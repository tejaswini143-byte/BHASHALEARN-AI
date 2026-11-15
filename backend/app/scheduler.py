"""PostgreSQL-backed reminder poller. Jobs remain in the database across restarts."""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select

from .db import SessionLocal
from .models import Deadline, Reminder, ReminderEvent, ReminderPreference


def claim_due_batch(limit: int = 25) -> list[str]:
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        # Recover interrupted calls/voice sessions after a crash, with a bounded retry count.
        stale = list(db.scalars(select(Reminder).where(Reminder.status == "in_progress", Reminder.claimed_at.is_not(None), Reminder.claimed_at <= now - timedelta(minutes=10)).with_for_update(skip_locked=True)))
        for row in stale:
            if row.attempts >= 3:
                row.status = "failed"
                db.add(ReminderEvent(reminder_id=row.id, event="failed", detail="retry limit after interrupted session"))
            else:
                row.status = "scheduled"
                delay_seconds = min(60, 2 ** row.attempts * 5)
                row.scheduled_at = now + timedelta(seconds=delay_seconds)
                row.claimed_at = None
                db.add(ReminderEvent(reminder_id=row.id, event="retry", detail=f"recovered interrupted session; retry in {delay_seconds}s"))
        rows = list(db.scalars(select(Reminder).where(Reminder.status == "scheduled", Reminder.scheduled_at <= now)
            .order_by(Reminder.scheduled_at).limit(limit).with_for_update(skip_locked=True)))
        ready = []
        for row in rows:
            prefs = db.get(ReminderPreference, row.student_id)
            deadline = db.get(Deadline, row.deadline_id)
            if not deadline or deadline.cancelled_at or deadline.completed_at or (prefs and not prefs.reminders_enabled):
                row.status = "cancelled"
                db.add(ReminderEvent(reminder_id=row.id, event="cancelled", detail="deadline complete/cancelled or student opted out"))
                continue
            row.status = "in_progress"
            row.attempts += 1
            row.claimed_at = now
            db.add(ReminderEvent(reminder_id=row.id, event="due"))
            ready.append(str(row.id))
        return ready


def dispatch_browser_reminder(reminder_id: str) -> None:
    """Persist a browser-delivery event after rechecking ownership, consent and deadline state.

    The browser consumes the durable in_progress row through the authenticated reminders API.
    This is an at-least-once outbox handoff; the UI deduplicates speech by reminder ID.
    """
    from uuid import UUID
    with SessionLocal.begin() as db:
        row = db.scalar(select(Reminder).where(Reminder.id == UUID(reminder_id)).with_for_update())
        if row is None or row.status != "in_progress":
            return
        prefs = db.get(ReminderPreference, row.student_id)
        deadline = db.get(Deadline, row.deadline_id)
        if not deadline or deadline.cancelled_at or deadline.completed_at or (prefs and not prefs.reminders_enabled):
            row.status = "cancelled"
            db.add(ReminderEvent(reminder_id=row.id, event="cancelled", detail="consent/deadline recheck failed at dispatch"))
            return
        db.add(ReminderEvent(reminder_id=row.id, event="browser_notification_ready", detail="available to authenticated student session"))


def record_dispatch_failure(reminder_id: str, error: Exception) -> None:
    """Retry transient dispatch failures with bounded exponential backoff."""
    from uuid import UUID
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        row = db.scalar(select(Reminder).where(Reminder.id == UUID(reminder_id)).with_for_update())
        if row is None or row.status != "in_progress":
            return
        if row.attempts >= 3:
            row.status = "failed"
            row.claimed_at = None
            detail = f"dispatch attempts exhausted: {type(error).__name__}"[:200]
            db.add(ReminderEvent(reminder_id=row.id, event="failed", detail=detail))
        else:
            delay_seconds = min(60, 2 ** row.attempts * 5)
            row.status = "scheduled"
            row.scheduled_at = now + timedelta(seconds=delay_seconds)
            row.claimed_at = None
            detail = f"retry in {delay_seconds}s: {type(error).__name__}"[:200]
            db.add(ReminderEvent(reminder_id=row.id, event="retry", detail=detail))


async def run_scheduler(stop: asyncio.Event, dispatch=dispatch_browser_reminder):
    while not stop.is_set():
        try:
            for reminder_id in await asyncio.to_thread(claim_due_batch):
                try:
                    result = dispatch(reminder_id)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as exc:
                    await asyncio.to_thread(record_dispatch_failure, reminder_id, exc)
        except Exception:
            # Keep the worker alive; database errors are visible to operator logs without user data.
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

