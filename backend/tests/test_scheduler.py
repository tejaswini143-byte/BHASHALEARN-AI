import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Reminder, ReminderEvent
from app.scheduler import claim_due_batch, dispatch_browser_reminder, record_dispatch_failure, run_scheduler


def test_due_reminder_is_claimed_once_and_browser_delivery_is_persisted(scheduler_db):
    factory, _, ids = scheduler_db
    assert claim_due_batch() == [str(ids["reminder_id"])]
    assert claim_due_batch() == []
    dispatch_browser_reminder(str(ids["reminder_id"]))
    with factory() as db:
        row = db.get(Reminder, ids["reminder_id"])
        events = list(db.scalars(select(ReminderEvent).where(ReminderEvent.reminder_id == row.id)))
        assert row.status == "in_progress"
        assert {event.event for event in events} >= {"due", "browser_notification_ready"}


def test_retry_uses_bounded_exponential_delay(scheduler_db):
    factory, _, ids = scheduler_db
    claim_due_batch()
    record_dispatch_failure(str(ids["reminder_id"]), TimeoutError())
    with factory() as db:
        row = db.get(Reminder, ids["reminder_id"])
        assert row.status == "scheduled"
        scheduled_at = row.scheduled_at.replace(tzinfo=timezone.utc) if row.scheduled_at.tzinfo is None else row.scheduled_at
        assert 9 <= (scheduled_at - datetime.now(timezone.utc)).total_seconds() <= 11
        assert list(db.scalars(select(ReminderEvent).where(ReminderEvent.event == "retry")))


def test_restart_recovers_stale_claim_and_retries(scheduler_db):
    factory, engine, ids = scheduler_db
    claim_due_batch()
    with factory.begin() as db:
        row = db.get(Reminder, ids["reminder_id"])
        row.claimed_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    engine.dispose()
    assert claim_due_batch() == []
    with factory() as db:
        row = db.get(Reminder, ids["reminder_id"])
        assert row.status == "scheduled"
        assert row.attempts == 1
        assert list(db.scalars(select(ReminderEvent).where(ReminderEvent.event == "retry")))
    with factory.begin() as db:
        row = db.get(Reminder, ids["reminder_id"])
        row.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert claim_due_batch() == [str(ids["reminder_id"])]
    with factory() as db:
        row = db.get(Reminder, ids["reminder_id"])
        assert row.status == "in_progress"
        assert row.attempts == 2


def test_scheduler_uses_real_dispatch_and_stops_cleanly(monkeypatch):
    stop = asyncio.Event()
    dispatched = []

    def claim():
        stop.set()
        return ["job-1"]

    def dispatch(job_id):
        dispatched.append(job_id)

    monkeypatch.setattr("app.scheduler.claim_due_batch", claim)
    asyncio.run(run_scheduler(stop, dispatch))
    assert dispatched == ["job-1"]
