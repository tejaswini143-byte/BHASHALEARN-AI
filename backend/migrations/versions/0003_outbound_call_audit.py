"""Add guarded outbound call audit records."""
from alembic import op
import sqlalchemy as sa

revision = "0003_outbound_call_audit"
down_revision = "0002_voice_and_scheduler"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "call_attempts",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("voice_session_id", sa.Uuid(as_uuid=True), sa.ForeignKey("voice_sessions.id", ondelete="SET NULL")),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("room_name", sa.String(128), nullable=False, unique=True),
        sa.Column("participant_identity", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("failure_detail", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_call_attempts_student_id", "call_attempts", ["student_id"])
    op.create_index("ix_call_attempts_reminder_id", "call_attempts", ["reminder_id"])
    op.create_index("ix_call_attempts_voice_session_id", "call_attempts", ["voice_session_id"])
    op.create_index("ix_call_attempts_status", "call_attempts", ["status"])
    op.create_index("ix_call_attempts_created_at", "call_attempts", ["created_at"])


def downgrade() -> None:
    op.drop_table("call_attempts")
