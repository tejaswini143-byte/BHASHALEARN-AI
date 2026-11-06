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
    assert {"students", "courses", "learning_sessions", "chat_messages", "learning_progress", "documents", "document_pages"}.issubset(inspect(engine).get_table_names())
    engine.dispose()
    command.downgrade(cfg, "base")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    assert "students" not in inspect(engine).get_table_names()
    assert "documents" not in inspect(engine).get_table_names()
    engine.dispose()


def test_document_migration_upgrade_downgrade_and_reupgrade(tmp_path, monkeypatch):
    db_file = tmp_path / "documents-migration.db"
    monkeypatch.setenv("BHASHALEARN_DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("backend/alembic.ini")
    command.upgrade(cfg, "0006_adaptive_learning_memory")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    before = set(inspect(engine).get_table_names())
    assert "learning_assessment_attempts" in before
    assert "documents" not in before
    engine.dispose()

    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    inspector = inspect(engine)
    assert {"documents", "document_pages", "learning_assessment_attempts", "learning_progress"}.issubset(inspector.get_table_names())
    assert "ix_documents_student_id" in {item["name"] for item in inspector.get_indexes("documents")}
    assert "ix_document_pages_document_id" in {item["name"] for item in inspector.get_indexes("document_pages")}
    assert {item["name"] for item in inspector.get_unique_constraints("document_pages")} == {"uq_document_pages_document_page"}
    engine.dispose()

    command.downgrade(cfg, "0006_adaptive_learning_memory")
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    remaining = set(inspect(engine).get_table_names())
    assert "documents" not in remaining and "document_pages" not in remaining
    assert {"students", "learning_progress", "learning_assessment_attempts"}.issubset(remaining)
    engine.dispose()
    command.upgrade(cfg, "head")
