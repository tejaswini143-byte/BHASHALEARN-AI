"""Initial BHASHALEARN relational data model."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    sessions: Mapped[list["LearningSession"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    language: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    student: Mapped[Student] = relationship(back_populates="sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    session: Mapped[LearningSession] = relationship(back_populates="messages")


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = (UniqueConstraint("student_id", "topic", name="uq_progress_student_topic"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class StudentPreferences(Base):
    """One set of learning preferences per student."""
    __tablename__ = "student_preferences"

    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_language: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    learning_level: Mapped[str] = mapped_column(String(16), default="beginner", nullable=False)
    learning_goal: Mapped[str | None] = mapped_column(String(300))


class Lesson(Base):
    """Ordered lesson within a course."""
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("course_id", "position", name="uq_lesson_course_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    course: Mapped[Course] = relationship()


class LearningMemory(Base):
    __tablename__ = "learning_memories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class SessionVisualState(Base):
    """One allowlisted built-in visual lesson selection for a learning session."""
    __tablename__ = "session_visual_states"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    visual_key: Mapped[str] = mapped_column(String(80), nullable=False)
    start_node: Mapped[str | None] = mapped_column(String(1))
    end_node: Mapped[str | None] = mapped_column(String(1))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
