"""Track student mission rewards with idempotent completion records."""
from alembic import op
import sqlalchemy as sa

revision = "0010_mission_completions"
down_revision = "0009_learning_pace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mission_completions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mission_id", sa.String(100), nullable=False),
        sa.Column("xp_awarded", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "mission_id", name="uq_mission_completion_student_mission"),
        sa.CheckConstraint("xp_awarded >= 0", name="ck_mission_completion_xp_nonnegative"),
    )
    op.create_index("ix_mission_completions_student_id", "mission_completions", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_mission_completions_student_id", table_name="mission_completions")
    op.drop_table("mission_completions")
