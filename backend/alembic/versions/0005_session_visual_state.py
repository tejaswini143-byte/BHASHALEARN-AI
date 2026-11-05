"""Persist built-in visual lesson selection per learning session."""
from alembic import op
import sqlalchemy as sa

revision = "0005_session_visual_state"
down_revision = "0004_learning_memories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_visual_states",
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("visual_key", sa.String(80), nullable=False),
        sa.Column("start_node", sa.String(1), nullable=True),
        sa.Column("end_node", sa.String(1), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("session_visual_states")
