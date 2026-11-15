"""Add scheduler leases and LiveKit voice session history."""
from alembic import op
import sqlalchemy as sa

revision = "0002_voice_and_scheduler"
down_revision = "0001_deadline_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reminder_preferences", sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("deadlines", sa.Column("reminder_minutes_before", sa.Integer(), nullable=False, server_default="1440"))
    op.add_column("reminders", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reminders", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_reminders_claimed_at", "reminders", ["claimed_at"])
    op.create_table(
        "voice_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reminder_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reminders.id", ondelete="SET NULL")),
        sa.Column("room_name", sa.String(128), nullable=False, unique=True),
        sa.Column("language", sa.String(12), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="creating"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_voice_sessions_student_id", "voice_sessions", ["student_id"])
    op.create_index("ix_voice_sessions_reminder_id", "voice_sessions", ["reminder_id"])
    op.create_index("ix_voice_sessions_status", "voice_sessions", ["status"])


def downgrade() -> None:
    op.drop_table("voice_sessions")
    op.drop_index("ix_reminders_claimed_at", table_name="reminders")
    op.drop_column("reminders", "updated_at")
    op.drop_column("reminders", "claimed_at")
    op.drop_column("deadlines", "reminder_minutes_before")
    op.drop_column("reminder_preferences", "reminders_enabled")
