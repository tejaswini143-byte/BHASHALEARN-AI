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
        stale = list(db.scalars(select(Reminder).where(Reminder.status == "in_progress", Reminder.updated_at <= now - timedelta(minutes=10)).with_for_update(skip_locked=True)))
        for row in stale:
            if row.attempts >= 3:
                row.status = "failed"
                db.add(ReminderEvent(reminder_id=row.id, event="failed", detail="retry limit after interrupted session"))
            else:
                row.status = "scheduled"
                row.scheduled_at = now
                db.add(ReminderEvent(reminder_id=row.id, event="retry", detail="recovered interrupted session"))
        rows = list(db.scalars(select(Reminder).where(Reminder.status == "scheduled", Reminder.scheduled_at <= now)
            .order_by(Reminder.scheduled_at).limit(limit).with_for_update(skip_locked=True)))
        ready = []
        for row in rows:
            prefs = db.get(ReminderPreference, row.student_id)
            deadline = db.get(Deadline, row.deadline_id)
            if not deadline or deadline.cancelled_at or deadline.completed_at or (prefs and prefs.opted_out_at):
                row.status = "cancelled"
                db.add(ReminderEvent(reminder_id=row.id, event="cancelled", detail="deadline complete/cancelled or student opted out"))
                continue
            row.status = "in_progress"
            row.attempts += 1
            db.add(ReminderEvent(reminder_id=row.id, event="due"))
            ready.append(str(row.id))
        return ready


async def run_scheduler(stop: asyncio.Event, dispatch):
    while not stop.is_set():
        try:
            for reminder_id in await asyncio.to_thread(claim_due_batch):
                await dispatch(reminder_id)
        except Exception:
            # Keep the service alive; the durable rows are retried on a later poll.
            pass
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass

