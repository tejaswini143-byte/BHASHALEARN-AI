"""Student scoped public research sessions and approval proposals."""
from alembic import op
import sqlalchemy as sa

revision = "0011_int24_research"
down_revision = "0010_mission_completions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("research_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider_mode", sa.String(24)), sa.Column("summary_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_research_sessions_student_created", "research_sessions", ["student_id", "created_at"])
    op.create_table("research_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("research_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False), sa.Column("canonical_url", sa.String(2048), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=False), sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "canonical_url", name="uq_research_source_session_url"))
    op.create_index("ix_research_sources_session_id", "research_sources", ["session_id"])
    op.create_table("research_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_session_id", sa.String(36), sa.ForeignKey("research_sessions.id", ondelete="SET NULL")),
        sa.Column("action_type", sa.String(40), nullable=False), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("approval_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executable", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("student_id", "idempotency_key", name="uq_research_task_student_idempotency"),
        sa.CheckConstraint("status IN ('drafted','awaiting_approval','approved','executing','completed','failed','cancelled')", name="ck_research_task_status"))
    op.create_index("ix_research_tasks_student_created", "research_tasks", ["student_id", "created_at"])
    op.create_table("research_audit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("research_tasks.id", ondelete="SET NULL")),
        sa.Column("event", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_research_audit_student_id", "research_audit", ["student_id"])
    op.create_index("ix_research_audit_task_id", "research_audit", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_research_audit_task_id", table_name="research_audit")
    op.drop_index("ix_research_audit_student_id", table_name="research_audit")
    op.drop_table("research_audit")
    op.drop_index("ix_research_tasks_student_created", table_name="research_tasks")
    op.drop_table("research_tasks")
    op.drop_index("ix_research_sources_session_id", table_name="research_sources")
    op.drop_table("research_sources")
    op.drop_index("ix_research_sessions_student_created", table_name="research_sessions")
    op.drop_table("research_sessions")
