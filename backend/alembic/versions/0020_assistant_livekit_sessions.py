"""Persist authenticated browser LiveKit reminder sessions."""
from alembic import op
import sqlalchemy as sa

revision = "0020_assistant_livekit_sessions"
down_revision = "0019_explicit_call_microphone_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_livekit_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deadline_id", sa.String(36), sa.ForeignKey("assistant_deadlines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_name", sa.String(128), nullable=False),
        sa.Column("language", sa.String(16), nullable=False, server_default="mixed"),
        sa.Column("status", sa.String(24), nullable=False, server_default="creating"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("room_name", name="uq_assistant_livekit_room"),
    )
    op.create_index("ix_assistant_livekit_owner_created", "assistant_livekit_sessions", ["student_id", "created_at"])
    # Constraint creation through op.create_unique_constraint is unsupported by
    # SQLite's ALTER TABLE implementation. Batch mode emits native ALTERs on
    # PostgreSQL and safely rebuilds the table for SQLite migration tests.
    with op.batch_alter_table("assistant_call_attempts") as batch:
        batch.add_column(sa.Column(
            "livekit_session_id", sa.String(36),
            sa.ForeignKey(
                "assistant_livekit_sessions.id", ondelete="SET NULL",
                name="fk_assistant_call_attempts_livekit_session_id",
            ), nullable=True,
        ))
        batch.add_column(sa.Column("participant_identity", sa.String(128), nullable=True))
        batch.create_unique_constraint(
            "uq_assistant_call_participant_identity", ["participant_identity"]
        )


def downgrade() -> None:
    with op.batch_alter_table("assistant_call_attempts") as batch:
        batch.drop_constraint("uq_assistant_call_participant_identity", type_="unique")
        batch.drop_column("participant_identity")
        batch.drop_column("livekit_session_id")
    op.drop_index("ix_assistant_livekit_owner_created", table_name="assistant_livekit_sessions")
    op.drop_table("assistant_livekit_sessions")
