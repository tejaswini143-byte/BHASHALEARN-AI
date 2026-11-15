from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import Deadline, Reminder, Student
import app.scheduler as scheduler


@pytest.fixture
def scheduler_db(monkeypatch, tmp_path):
    path = tmp_path / "scheduler-test.sqlite3"
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(scheduler, "SessionLocal", factory)
    with factory.begin() as db:
        student = Student(id=uuid4(), email="scheduler@example.com", password_hash="not-a-real-password-hash")
        db.add(student)
        db.flush()
        deadline = Deadline(student_id=student.id, title="Math assignment", kind="assignment",
                            due_at=datetime.now(timezone.utc) + timedelta(hours=2), timezone="Asia/Kolkata")
        db.add(deadline)
        db.flush()
        reminder = Reminder(deadline_id=deadline.id, student_id=student.id,
                            scheduled_at=datetime.now(timezone.utc) - timedelta(seconds=1),
                            channel="browser", status="scheduled", attempts=0,
                            idempotency_key=f"test:{uuid4()}")
        db.add(reminder)
        db.flush()
        result = {"student_id": student.id, "deadline_id": deadline.id, "reminder_id": reminder.id}
    try:
        yield factory, engine, result
    finally:
        engine.dispose()
