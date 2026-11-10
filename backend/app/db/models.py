"""Initial BHASHALEARN relational data model."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, TypeDecorator
from pgvector.sqlalchemy import Vector

from .base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class EmbeddingVector(TypeDecorator):
    """Use pgvector in production and JSON vectors for SQLite unit tests."""
    impl = JSON
    cache_ok = True
    comparator_factory = Vector.comparator_factory

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(768))
        return dialect.type_descriptor(JSON())


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

    normalized_topic_key: Mapped[str] = mapped_column(String(200), default="", nullable=False, index=True)
    evidence_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incorrect_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ambiguous_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(24), default="unassessed", nullable=False)
    last_assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LearningAssessmentAttempt(Base):
    __tablename__ = "learning_assessment_attempts"
    __table_args__ = (UniqueConstraint("student_id", "idempotency_key", name="uq_assessment_student_idempotency"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False)
    session_id: Mapped[str] = mapped_column(ForeignKey("learning_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_topic_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    submitted_answer: Mapped[str | None] = mapped_column(String(500))
    is_correct: Mapped[bool | None] = mapped_column(nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MissionCompletion(Base):
    """An idempotent XP award for one student's mission instance."""
    __tablename__ = "mission_completions"
    __table_args__ = (
        UniqueConstraint("student_id", "mission_id", name="uq_mission_completion_student_mission"),
        CheckConstraint("xp_awarded >= 0", name="ck_mission_completion_xp_nonnegative"),
        Index("ix_mission_completions_student_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    mission_id: Mapped[str] = mapped_column(String(100), nullable=False)
    xp_awarded: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ResearchSession(Base):
    """Private, student-owned public web research session."""
    __tablename__ = "research_sessions"
    __table_args__ = (Index("ix_research_sessions_student_created", "student_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(String(1000), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="drafted")
    provider_mode: Mapped[str | None] = mapped_column(String(24))
    summary_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    sources: Mapped[list["ResearchSourceRecord"]] = relationship(cascade="all, delete-orphan")


class ResearchSourceRecord(Base):
    __tablename__ = "research_sources"
    __table_args__ = (UniqueConstraint("session_id", "canonical_url", name="uq_research_source_session_url"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    publisher: Mapped[str] = mapped_column(String(255), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResearchTask(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key", name="uq_research_task_student_idempotency"),
        CheckConstraint("status IN ('drafted','awaiting_approval','approved','executing','completed','failed','cancelled')", name="ck_research_task_status"),
        Index("ix_research_tasks_student_created", "student_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    research_session_id: Mapped[str | None] = mapped_column(ForeignKey("research_sessions.id", ondelete="SET NULL"))
    action_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="drafted")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    approval_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    executable: Mapped[bool] = mapped_column(default=False, nullable=False)


class ResearchAudit(Base):
    __tablename__ = "research_audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("research_tasks.id", ondelete="SET NULL"), index=True)
    event: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)



class CareerGoal(Base):
    """Private career goal and its latest catalog-grounded roadmap snapshot."""
    __tablename__ = "career_goals"
    __table_args__ = (Index("ix_career_goals_student_active", "student_id", "active"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    career_key: Mapped[str] = mapped_column(String(64), nullable=False)
    custom_goal: Mapped[str | None] = mapped_column(String(160))
    education_level: Mapped[str] = mapped_column(String(32), nullable=False)
    interests_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    weekly_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False)
    target_date: Mapped[str | None] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    roadmap_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class StudentSkillProfile(Base):
    """Student-reported proficiency; this table never grants verified mastery."""
    __tablename__ = "student_skill_profiles"
    __table_args__ = (UniqueConstraint("student_id", "skill_key", name="uq_student_skill_profile"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    skill_key: Mapped[str] = mapped_column(String(64), nullable=False)
    proficiency: Mapped[str] = mapped_column(String(24), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class CareerMilestoneCompletion(Base):
    """Idempotent student-owned milestone completion record."""
    __tablename__ = "career_milestone_completions"
    __table_args__ = (UniqueConstraint("student_id", "goal_id", "milestone_id", name="uq_career_milestone_student_goal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[str] = mapped_column(ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False)
    milestone_id: Mapped[str] = mapped_column(String(120), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CareerLessonCompletion(Base):
    """Idempotent completion of a real catalog lesson in a student's goal."""
    __tablename__ = "career_lesson_completions"
    __table_args__ = (UniqueConstraint("student_id", "goal_id", "lesson_id", name="uq_career_lesson_student_goal"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[str] = mapped_column(ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CareerStudyWeek(Base):
    """Student-entered weekly minutes, used as a replanning signal."""
    __tablename__ = "career_study_weeks"
    __table_args__ = (
        UniqueConstraint("student_id", "goal_id", "week_start", name="uq_career_study_week_student_goal"),
        CheckConstraint("target_minutes >= 30 AND target_minutes <= 2400", name="ck_career_study_target_minutes"),
        CheckConstraint("studied_minutes >= 0 AND studied_minutes <= 2400", name="ck_career_studied_minutes"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    goal_id: Mapped[str] = mapped_column(ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False)
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)
    target_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    studied_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class StudentPreferences(Base):
    """One set of learning preferences per student."""
    __tablename__ = "student_preferences"

    student_id: Mapped[str] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), primary_key=True
    )
    preferred_language: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    learning_level: Mapped[str] = mapped_column(String(16), default="beginner", nullable=False)
    learning_pace: Mapped[str] = mapped_column(String(16), default="steady", nullable=False)
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


class SessionVoiceState(Base):
    """Voice playback and interruption checkpoint scoped to one learning session."""
    __tablename__ = "session_voice_states"

    session_id: Mapped[str] = mapped_column(
        ForeignKey("learning_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_step: Mapped[str] = mapped_column(String(120), default="introduction", nullable=False)
    student_question: Mapped[str | None] = mapped_column(Text)
    active_response_language: Mapped[str] = mapped_column(String(16), default="mixed", nullable=False)
    playback_state: Mapped[str] = mapped_column(String(20), default="idle", nullable=False)
    voice_transcript: Mapped[str | None] = mapped_column(Text)
    checkpoint_message_id: Mapped[str | None] = mapped_column(String(36))
    checkpoint_playback_ms: Mapped[int | None] = mapped_column(Integer)
    resume_status: Mapped[str] = mapped_column(String(28), default="none", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class Document(Base):
    """Private PDF metadata owned by one student."""
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("file_size_bytes >= 0", name="ck_documents_file_size_nonnegative"),
        CheckConstraint("page_count IS NULL OR page_count >= 0", name="ck_documents_page_count_nonnegative"),
        CheckConstraint("processing_status IN ('processed', 'text_extraction_unavailable', 'failed')", name="ck_documents_processing_status"),
        Index("uq_documents_id_student_id", "id", "student_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), default="application/pdf", nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processing_status: Mapped[str] = mapped_column(String(40), nullable=False)
    processing_error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentPage(Base):
    """Page-level extracted text for a private document."""
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_pages_document_page"),
        CheckConstraint("page_number >= 1", name="ck_document_pages_page_number_positive"),
        CheckConstraint("character_count >= 0", name="ck_document_pages_character_count_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    document: Mapped[Document] = relationship(back_populates="pages")


class DocumentIndexGeneration(Base):
    """A complete or in-progress version of one document's vector index."""
    __tablename__ = "document_index_generations"
    __table_args__ = (
        UniqueConstraint("id", "document_id", "student_id", name="uq_document_index_generation_owner"),
        ForeignKeyConstraint(["document_id", "student_id"], ["documents.id", "documents.student_id"], ondelete="CASCADE"),
        CheckConstraint("status IN ('building', 'ready', 'failed')", name="ck_document_index_generation_status"),
        CheckConstraint("embedding_dimensions = 768", name="ck_document_index_generation_dimensions"),
        Index("ix_document_index_generations_owner_status", "student_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="building")
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=768)
    chunking_version: Mapped[str] = mapped_column(String(40), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DocumentIndexState(Base):
    """Latest indexing attempt and atomically active generation per document."""
    __tablename__ = "document_index_states"
    __table_args__ = (
        ForeignKeyConstraint(["document_id", "student_id"], ["documents.id", "documents.student_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["active_generation_id", "document_id", "student_id"],
            ["document_index_generations.id", "document_index_generations.document_id", "document_index_generations.student_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("status IN ('pending', 'processing', 'ready', 'failed')", name="ck_document_index_state_status"),
    )

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    active_generation_id: Mapped[str | None] = mapped_column(String(36))
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentChunk(Base):
    """Student-owned text chunk and its Gemini embedding."""
    __tablename__ = "document_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["generation_id", "document_id", "student_id"],
            ["document_index_generations.id", "document_index_generations.document_id", "document_index_generations.student_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("generation_id", "ordinal", name="uq_document_chunks_generation_ordinal"),
        CheckConstraint("page_number >= 1", name="ck_document_chunks_page_positive"),
        CheckConstraint("ordinal >= 0", name="ck_document_chunks_ordinal_nonnegative"),
        CheckConstraint("char_count > 0", name="ck_document_chunks_char_count_positive"),
        CheckConstraint("embedding_dimensions = 768", name="ck_document_chunks_embedding_dimensions"),
        Index("ix_document_chunks_owner_document", "student_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(36), nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(80), nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, nullable=False, default=768)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantSettings(Base):
    """Private assistant preferences and automation safety switches."""
    __tablename__ = "assistant_settings"

    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    modes_json: Mapped[str] = mapped_column(Text, default='["student"]', nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata", nullable=False)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    reminder_phone: Mapped[str | None] = mapped_column(String(32))
    phone_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    call_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_lead_minutes_json: Mapped[str] = mapped_column(Text, default="[1440,60]", nullable=False)
    quiet_start: Mapped[str | None] = mapped_column(String(5))
    quiet_end: Mapped[str | None] = mapped_column(String(5))
    enabled_integrations_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    email_policy: Mapped[str] = mapped_column(String(24), default="draft_only", nullable=False)
    notifications_json: Mapped[str] = mapped_column(Text, default='{"email":true,"call":false}', nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    paused: Mapped[bool] = mapped_column(default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class AssistantDeadline(Base):
    __tablename__ = "assistant_deadlines"
    __table_args__ = (
        UniqueConstraint("student_id", "dedupe_key", name="uq_assistant_deadline_owner_dedupe"),
        CheckConstraint("status IN ('upcoming','overdue','completed','canceled','needs_confirmation')", name="ck_assistant_deadline_status"),
        Index("ix_assistant_deadlines_owner_due", "student_id", "due_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(80), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="normal", nullable=False)
    category: Mapped[str] = mapped_column(String(40), default="personal", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="upcoming", nullable=False)
    source: Mapped[str] = mapped_column(String(24), default="manual", nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(255))
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantJob(Base):
    __tablename__ = "assistant_jobs"
    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key", name="uq_assistant_job_owner_idempotency"),
        Index("ix_assistant_jobs_due_status", "status", "run_at"),
        CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_assistant_job_attempts"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    deadline_id: Mapped[str | None] = mapped_column(ForeignKey("assistant_deadlines.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500))
    provider_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantAccount(Base):
    """Provider connection state only; credentials belong in a secret vault."""
    __tablename__ = "assistant_accounts"
    __table_args__ = (UniqueConstraint("student_id", "provider", name="uq_assistant_account_owner_provider"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="disconnected", nullable=False)
    account_email: Mapped[str | None] = mapped_column(String(320))
    cursor: Mapped[str | None] = mapped_column(String(255))
    sync_history_anchor: Mapped[str | None] = mapped_column(String(32))
    sync_page_token: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(String(200))
    access_token_enc: Mapped[str | None] = mapped_column(Text)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_scopes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class AssistantDraft(Base):
    __tablename__ = "assistant_drafts"
    __table_args__ = (Index("ix_assistant_drafts_owner_status", "student_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    thread_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    risk_category: Mapped[str] = mapped_column(String(32), default="low", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    rfc_message_id: Mapped[str | None] = mapped_column(String(998))
    references_header: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantAuditEvent(Base):
    __tablename__ = "assistant_audit_events"
    __table_args__ = (Index("ix_assistant_audit_owner_created", "student_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    details_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantOAuthState(Base):
    __tablename__ = "assistant_oauth_states"
    __table_args__ = (
        UniqueConstraint("state_hash", name="uq_assistant_oauth_state_hash"),
        Index("ix_assistant_oauth_owner_expiry", "student_id", "expires_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_scopes: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantEmailMessage(Base):
    __tablename__ = "assistant_email_messages"
    __table_args__ = (
        UniqueConstraint("student_id", "message_ref", name="uq_assistant_email_owner_message"),
        Index("ix_assistant_email_owner_date", "student_id", "internal_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    message_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    thread_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    sender: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    snippet: Mapped[str] = mapped_column(String(1200), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    needs_reply: Mapped[bool] = mapped_column(default=False, nullable=False)
    internal_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rfc_message_id: Mapped[str | None] = mapped_column(String(998))
    references_header: Mapped[str | None] = mapped_column(String(2000))
    history_id: Mapped[str | None] = mapped_column(String(32))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantDeadlineCandidate(Base):
    __tablename__ = "assistant_deadline_candidates"
    __table_args__ = (
        UniqueConstraint("student_id", "source_ref", "candidate_hash", name="uq_assistant_candidate_source_hash"),
        Index("ix_assistant_candidate_owner_status", "student_id", "status"),
        CheckConstraint("status IN ('needs_confirmation','confirmed','rejected')", name="ck_assistant_candidate_status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    date_phrase: Mapped[str] = mapped_column(String(160), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="needs_confirmation", nullable=False)
    confirmed_deadline_id: Mapped[str | None] = mapped_column(ForeignKey("assistant_deadlines.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class AssistantCallAttempt(Base):
    __tablename__ = "assistant_call_attempts"
    __table_args__ = (
        UniqueConstraint("student_id", "idempotency_key", name="uq_assistant_call_owner_idempotency"),
        UniqueConstraint("job_id", "attempt_number", name="uq_assistant_call_job_attempt"),
        Index("ix_assistant_call_owner_created", "student_id", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("assistant_jobs.id", ondelete="CASCADE"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    destination: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_sid: Mapped[str | None] = mapped_column(String(64), unique=True)
    callback_sequence: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(64))
    provider_status: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class AssistantCalendarEvent(Base):
    __tablename__ = "assistant_calendar_events"
    __table_args__ = (
        UniqueConstraint("student_id", "external_id", name="uq_assistant_calendar_owner_external"),
        UniqueConstraint("student_id", "dedupe_key", name="uq_assistant_calendar_owner_dedupe"),
        Index("ix_assistant_calendar_owner_start", "student_id", "starts_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone_name: Mapped[str] = mapped_column(String(80), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
