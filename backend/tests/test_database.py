"""BE-02 database smoke tests with an isolated SQLite database."""
import pytest
from alembic import command
from alembic.config import Config
import sqlalchemy as sa
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
    command.upgrade(cfg, "0005_session_visual_state")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO students (id, email, display_name, password_hash, created_at) "
            "VALUES ('student-1', 'migration@example.com', 'Migration learner', NULL, '2026-01-01 00:00:00')"
        ))
        connection.execute(sa.text(
            "INSERT INTO learning_progress (id, student_id, topic, mastery_score, attempts, updated_at) "
            "VALUES ('progress-1', 'student-1', 'Fractions', 40, 2, '2026-01-01 00:00:00'), "
            "('progress-2', 'student-1', ' fractions ', 80, 4, '2026-01-02 00:00:00')"
        ))
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    tables = inspect(engine).get_table_names()
    assert {"students", "courses", "learning_sessions", "chat_messages", "learning_progress", "learning_assessment_attempts", "learning_progress_legacy_duplicates"}.issubset(tables)
    assert "topic_key" in {column["name"] for column in inspect(engine).get_columns("learning_progress")}
    with engine.connect() as connection:
        current = connection.execute(sa.text("SELECT topic, mastery_score, attempts, evidence_count FROM learning_progress")).mappings().one()
        archived = connection.execute(sa.text("SELECT topic, mastery_score, attempts FROM learning_progress_legacy_duplicates")).mappings().one()
        assert current["topic"] == "Fractions"
        assert current["mastery_score"] == 80 and current["attempts"] == 4 and current["evidence_count"] == 0
        assert archived["topic"] == " fractions " and archived["mastery_score"] == 80 and archived["attempts"] == 4
    engine.dispose()
    command.downgrade(cfg, "0005_session_visual_state")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    with engine.connect() as connection:
        restored = connection.execute(sa.text("SELECT id, topic, mastery_score, attempts FROM learning_progress ORDER BY id")).mappings().all()
        assert len(restored) == 2
        assert {row["id"] for row in restored} == {"progress-1", "progress-2"}
    assert "learning_progress_legacy_duplicates" not in inspect(engine).get_table_names()
    engine.dispose()
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    assert "students" not in inspect(engine).get_table_names()
    engine.dispose()
