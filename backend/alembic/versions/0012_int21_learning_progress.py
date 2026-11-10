"""Record career lesson and weekly study progress for adaptive replanning."""
from alembic import op
import sqlalchemy as sa

revision = "0012_int21_learning_progress"
down_revision = "0011_int21_career_roadmap"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_lesson_completions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lesson_id", sa.String(36), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "goal_id", "lesson_id", name="uq_career_lesson_student_goal"),
    )
    op.create_table(
        "career_study_weeks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.String(10), nullable=False),
        sa.Column("target_minutes", sa.Integer(), nullable=False),
        sa.Column("studied_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "goal_id", "week_start", name="uq_career_study_week_student_goal"),
        sa.CheckConstraint("target_minutes >= 30 AND target_minutes <= 2400", name="ck_career_study_target_minutes"),
        sa.CheckConstraint("studied_minutes >= 0 AND studied_minutes <= 2400", name="ck_career_studied_minutes"),
    )
    op.create_index("ix_career_lesson_completions_student_goal", "career_lesson_completions", ["student_id", "goal_id"])


def downgrade() -> None:
    op.drop_index("ix_career_lesson_completions_student_goal", table_name="career_lesson_completions")
    op.drop_table("career_study_weeks")
    op.drop_table("career_lesson_completions")
