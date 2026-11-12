"""Persist local reminder call sessions without telephone provider use."""
from alembic import op
import sqlalchemy as sa

revision = "0017_local_deadline_calls"
down_revision = "0016_course_learning_paths"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_local_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deadline_id", sa.String(36), sa.ForeignKey("assistant_deadlines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("assistant_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ringing"),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("turns_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("pending_reschedule_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_assistant_local_call_job"),
        sa.CheckConstraint(
            "status IN ('ringing','answered','snoozed','dismissed','ended','missed','failed')",
            name="ck_assistant_local_call_status",
        ),
    )
    op.create_index("ix_assistant_local_calls_owner_created", "assistant_local_calls", ["student_id", "created_at"])
    op.create_index("ix_assistant_local_calls_owner_status", "assistant_local_calls", ["student_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_assistant_local_calls_owner_status", table_name="assistant_local_calls")
    op.drop_index("ix_assistant_local_calls_owner_created", table_name="assistant_local_calls")
    op.drop_table("assistant_local_calls")
