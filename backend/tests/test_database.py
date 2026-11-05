"""BE-02 database smoke tests with an isolated SQLite database."""
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import ChatMessage, Course, LearningProgress, LearningSession, Student


def test_schema_and_relationships(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        student = Student(email="student@example.test", display_name="Student")
        course = Course(title="Fractions")
        db.add_all([student, course])
        db.flush()
        lesson = LearningSession(student_id=student.id, course_id=course.id, topic="fractions")
        db.add(lesson)
        db.flush()
        db.add_all([
            ChatMessage(session_id=lesson.id, role="user", content="What is 1/2?"),
            LearningProgress(student_id=student.id, topic="fractions", mastery_score=0.5, attempts=1),
        ])
        db.commit()
        assert db.scalar(select(Student).where(Student.email == "student@example.test")) is not None
        assert db.scalar(select(ChatMessage).where(ChatMessage.session_id == lesson.id)).content == "What is 1/2?"
        assert db.scalar(select(LearningProgress)).attempts == 1
    engine.dispose()


def test_alembic_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_file = tmp_path / "migrated.db"
    monkeypatch.setenv("BHASHALEARN_DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("backend/alembic.ini")
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    assert {"students", "courses", "learning_sessions", "chat_messages", "learning_progress"}.issubset(inspect(engine).get_table_names())
    engine.dispose()
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    assert "students" not in inspect(engine).get_table_names()
    engine.dispose()
