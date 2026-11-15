"""Persist generated visual lesson snapshots and student progress."""
from alembic import op
import sqlalchemy as sa


revision = "0020_visual_lesson_session_state"
down_revision = "0019_explicit_call_microphone_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visual_lesson_session_states",
        sa.Column("session_id", sa.String(36), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("lesson_id", sa.String(80), nullable=False),
        sa.Column("lesson_json", sa.Text(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interactions_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("quiz_responses_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("current_step >= -1", name="ck_visual_lesson_session_step_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("visual_lesson_session_states")
