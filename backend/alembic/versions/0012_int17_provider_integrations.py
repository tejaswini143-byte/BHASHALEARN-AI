"""INT17 encrypted provider accounts, OAuth state, sync metadata and call history."""
from alembic import op
import sqlalchemy as sa

revision = "0012_int17_provider_integrations"
down_revision = "0011_int17_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assistant_jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assistant_accounts", sa.Column("access_token_enc", sa.Text(), nullable=True))
    op.add_column("assistant_accounts", sa.Column("refresh_token_enc", sa.Text(), nullable=True))
    op.add_column("assistant_accounts", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assistant_accounts", sa.Column("granted_scopes", sa.Text(), nullable=True))
    op.add_column("assistant_accounts", sa.Column("sync_history_anchor", sa.String(32), nullable=True))
    op.add_column("assistant_accounts", sa.Column("sync_page_token", sa.Text(), nullable=True))
    op.add_column("assistant_drafts", sa.Column("idempotency_key", sa.String(128), nullable=True))
    op.add_column("assistant_drafts", sa.Column("failure_code", sa.String(64), nullable=True))
    op.add_column("assistant_drafts", sa.Column("rfc_message_id", sa.String(998), nullable=True))
    op.add_column("assistant_drafts", sa.Column("references_header", sa.String(2000), nullable=True))
    op.create_unique_constraint("uq_assistant_drafts_owner_idempotency", "assistant_drafts", ["student_id", "idempotency_key"])
    op.create_unique_constraint("uq_assistant_drafts_provider_message", "assistant_drafts", ["student_id", "provider_message_id"])

    op.create_table(
        "assistant_oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False), sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False), sa.Column("requested_scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("state_hash", name="uq_assistant_oauth_state_hash"),
    )
    op.create_index("ix_assistant_oauth_owner_expiry", "assistant_oauth_states", ["student_id", "expires_at"])
    op.create_table(
        "assistant_email_messages",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_ref", sa.String(255), nullable=False), sa.Column("thread_ref", sa.String(255), nullable=False),
        sa.Column("sender", sa.String(320), nullable=False), sa.Column("subject", sa.String(500), nullable=False), sa.Column("snippet", sa.String(1200), nullable=False),
        sa.Column("category", sa.String(32), nullable=False), sa.Column("needs_reply", sa.Boolean(), nullable=False), sa.Column("internal_date", sa.DateTime(timezone=True)),
        sa.Column("rfc_message_id", sa.String(998)), sa.Column("references_header", sa.String(2000)), sa.Column("history_id", sa.String(32)),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "message_ref", name="uq_assistant_email_owner_message"),
    )
    op.create_index("ix_assistant_email_owner_date", "assistant_email_messages", ["student_id", "internal_date"])
    op.create_table(
        "assistant_deadline_candidates",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("date_phrase", sa.String(160), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("candidate_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("confirmed_deadline_id", sa.String(36), sa.ForeignKey("assistant_deadlines.id", ondelete="SET NULL")), sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "source_ref", "candidate_hash", name="uq_assistant_candidate_source_hash"),
        sa.CheckConstraint("status IN ('needs_confirmation','confirmed','rejected')", name="ck_assistant_candidate_status"),
    )
    op.create_index("ix_assistant_candidate_owner_status", "assistant_deadline_candidates", ["student_id", "status"])
    op.create_table(
        "assistant_call_attempts",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("assistant_jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False), sa.Column("destination", sa.String(32), nullable=False), sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider_sid", sa.String(64), unique=True), sa.Column("callback_sequence", sa.Integer(), nullable=False), sa.Column("failure_code", sa.String(64)),
        sa.Column("provider_status", sa.String(32)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "idempotency_key", name="uq_assistant_call_owner_idempotency"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_assistant_call_job_attempt"),
    )
    op.create_index("ix_assistant_call_owner_created", "assistant_call_attempts", ["student_id", "created_at"])
    op.create_table(
        "assistant_calendar_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("title", sa.String(500), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False), sa.Column("timezone_name", sa.String(80), nullable=False), sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "external_id", name="uq_assistant_calendar_owner_external"),
        sa.UniqueConstraint("student_id", "dedupe_key", name="uq_assistant_calendar_owner_dedupe"),
    )
    op.create_index("ix_assistant_calendar_owner_start", "assistant_calendar_events", ["student_id", "starts_at"])


def downgrade() -> None:
    op.drop_index("ix_assistant_calendar_owner_start", table_name="assistant_calendar_events")
    op.drop_table("assistant_calendar_events")
    op.drop_index("ix_assistant_call_owner_created", table_name="assistant_call_attempts")
    op.drop_table("assistant_call_attempts")
    op.drop_index("ix_assistant_candidate_owner_status", table_name="assistant_deadline_candidates")
    op.drop_table("assistant_deadline_candidates")
    op.drop_index("ix_assistant_email_owner_date", table_name="assistant_email_messages")
    op.drop_table("assistant_email_messages")
    op.drop_index("ix_assistant_oauth_owner_expiry", table_name="assistant_oauth_states")
    op.drop_table("assistant_oauth_states")
    op.drop_constraint("uq_assistant_drafts_provider_message", "assistant_drafts", type_="unique")
    op.drop_constraint("uq_assistant_drafts_owner_idempotency", "assistant_drafts", type_="unique")
    op.drop_column("assistant_drafts", "references_header")
    op.drop_column("assistant_drafts", "rfc_message_id")
    op.drop_column("assistant_drafts", "failure_code")
    op.drop_column("assistant_drafts", "idempotency_key")
    op.drop_column("assistant_accounts", "granted_scopes")
    op.drop_column("assistant_accounts", "sync_page_token")
    op.drop_column("assistant_accounts", "sync_history_anchor")
    op.drop_column("assistant_accounts", "token_expires_at")
    op.drop_column("assistant_accounts", "refresh_token_enc")
    op.drop_column("assistant_accounts", "access_token_enc")
    op.drop_column("assistant_jobs", "claimed_at")
