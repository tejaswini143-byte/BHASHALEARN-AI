"""Persist voice lesson checkpoints per learning session."""
from alembic import op
import sqlalchemy as sa

revision = "0011_session_voice_state"
down_revision = "0010_mission_completions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_voice_states",
        sa.Column("session_id", sa.String(36), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lesson_step", sa.String(120), nullable=False, server_default="introduction"),
        sa.Column("student_question", sa.Text(), nullable=True),
        sa.Column("active_response_language", sa.String(16), nullable=False, server_default="mixed"),
        sa.Column("playback_state", sa.String(20), nullable=False, server_default="idle"),
        sa.Column("voice_transcript", sa.Text(), nullable=True),
        sa.Column("checkpoint_message_id", sa.String(36), nullable=True),
        sa.Column("checkpoint_playback_ms", sa.Integer(), nullable=True),
        sa.Column("resume_status", sa.String(28), nullable=False, server_default="none"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("session_voice_states")
