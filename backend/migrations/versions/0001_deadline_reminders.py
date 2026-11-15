"""Create the base deadline-reminder schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_deadline_reminders"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "students",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.UniqueConstraint("email", name="uq_students_email"),
    )
    op.create_index("ix_students_email", "students", ["email"], unique=True)
    op.create_table(
        "reminder_preferences",
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("language", sa.String(12), nullable=False, server_default="te-IN"),
        sa.Column("voice_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("call_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("call_consent_at", sa.DateTime(timezone=True)),
        sa.Column("phone_e164", sa.String(20)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("opted_out_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "deadlines",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False, server_default="assignment"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_deadlines_student_id", "deadlines", ["student_id"])
    op.create_index("ix_deadlines_due_at", "deadlines", ["due_at"])
    op.create_table(
        "reminders",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("deadline_id", sa.Uuid(as_uuid=True), sa.ForeignKey("deadlines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("student_id", sa.Uuid(as_uuid=True), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="browser"),
        sa.Column("status", sa.String(24), nullable=False, server_default="scheduled"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("snoozed_until", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("deadline_id", "scheduled_at", "channel", name="uq_reminder_deadline_schedule_channel"),
        sa.UniqueConstraint("idempotency_key", name="uq_reminders_idempotency_key"),
    )
    op.create_index("ix_reminders_deadline_id", "reminders", ["deadline_id"])
    op.create_index("ix_reminders_student_id", "reminders", ["student_id"])
    op.create_index("ix_reminders_scheduled_at", "reminders", ["scheduled_at"])
    op.create_index("ix_reminders_status", "reminders", ["status"])
    op.create_table(
        "reminder_events",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("reminder_id", sa.Uuid(as_uuid=True), sa.ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reminder_events_reminder_id", "reminder_events", ["reminder_id"])


def downgrade() -> None:
    op.drop_table("reminder_events")
    op.drop_table("reminders")
    op.drop_table("deadlines")
    op.drop_table("reminder_preferences")
    op.drop_index("ix_students_email", table_name="students")
    op.drop_table("students")
