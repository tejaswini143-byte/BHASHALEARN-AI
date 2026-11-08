"""INT17 per-student assistant settings, deadlines, jobs and audit."""
from alembic import op
import sqlalchemy as sa

revision = "0011_int17_assistant"
down_revision = "0010_mission_completions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_settings",
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("modes_json", sa.Text(), nullable=False), sa.Column("timezone_name", sa.String(80), nullable=False),
        sa.Column("preferred_language", sa.String(16), nullable=False), sa.Column("reminder_phone", sa.String(32)),
        sa.Column("phone_verified", sa.Boolean(), nullable=False), sa.Column("call_consent_at", sa.DateTime(timezone=True)),
        sa.Column("reminder_lead_minutes_json", sa.Text(), nullable=False), sa.Column("quiet_start", sa.String(5)),
        sa.Column("quiet_end", sa.String(5)), sa.Column("enabled_integrations_json", sa.Text(), nullable=False),
        sa.Column("email_policy", sa.String(24), nullable=False), sa.Column("notifications_json", sa.Text(), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False), sa.Column("paused", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "assistant_deadlines",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.String(2000)), sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone_name", sa.String(80), nullable=False), sa.Column("priority", sa.String(16), nullable=False), sa.Column("category", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("source", sa.String(24), nullable=False), sa.Column("source_ref", sa.String(255)),
        sa.Column("dedupe_key", sa.String(64), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "dedupe_key", name="uq_assistant_deadline_owner_dedupe"),
        sa.CheckConstraint("status IN ('upcoming','overdue','completed','canceled','needs_confirmation')", name="ck_assistant_deadline_status"),
    )
    op.create_index("ix_assistant_deadlines_owner_due", "assistant_deadlines", ["student_id", "due_at"])
    op.create_table(
        "assistant_jobs",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deadline_id", sa.String(36), sa.ForeignKey("assistant_deadlines.id", ondelete="CASCADE")), sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False), sa.Column("run_at", sa.DateTime(timezone=True), nullable=False), sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("max_attempts", sa.Integer(), nullable=False), sa.Column("last_error", sa.String(500)),
        sa.Column("provider_status", sa.String(32)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "idempotency_key", name="uq_assistant_job_owner_idempotency"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_assistant_job_attempts"),
    )
    op.create_index("ix_assistant_jobs_due_status", "assistant_jobs", ["status", "run_at"])
    op.create_table(
        "assistant_accounts", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False), sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("account_email", sa.String(320)), sa.Column("cursor", sa.String(255)),
        sa.Column("last_error", sa.String(200)), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "provider", name="uq_assistant_account_owner_provider"),
    )
    op.create_index("ix_assistant_accounts_student_id", "assistant_accounts", ["student_id"])
    op.create_table(
        "assistant_drafts", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False), sa.Column("thread_ref", sa.String(255), nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False), sa.Column("subject", sa.String(500), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("risk_category", sa.String(32), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_id", sa.String(255)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_drafts_owner_status", "assistant_drafts", ["student_id", "status"])
    op.create_table(
        "assistant_audit_events", sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False), sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False), sa.Column("target_id", sa.String(36)), sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_assistant_audit_owner_created", "assistant_audit_events", ["student_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_assistant_audit_owner_created", table_name="assistant_audit_events")
    op.drop_table("assistant_audit_events")
    op.drop_index("ix_assistant_drafts_owner_status", table_name="assistant_drafts")
    op.drop_table("assistant_drafts")
    op.drop_index("ix_assistant_accounts_student_id", table_name="assistant_accounts")
    op.drop_table("assistant_accounts")
    op.drop_index("ix_assistant_jobs_due_status", table_name="assistant_jobs")
    op.drop_table("assistant_jobs")
    op.drop_index("ix_assistant_deadlines_owner_due", table_name="assistant_deadlines")
    op.drop_table("assistant_deadlines")
    op.drop_table("assistant_settings")
