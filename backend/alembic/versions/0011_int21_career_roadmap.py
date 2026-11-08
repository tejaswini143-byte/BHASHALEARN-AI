"""Student-owned career goals, skill profiles, and milestone records."""
from alembic import op
import sqlalchemy as sa

revision = "0011_int21_career_roadmap"
down_revision = "0010_mission_completions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "career_goals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("career_key", sa.String(64), nullable=False),
        sa.Column("custom_goal", sa.String(160)),
        sa.Column("education_level", sa.String(32), nullable=False),
        sa.Column("interests_json", sa.Text(), nullable=False),
        sa.Column("weekly_minutes", sa.Integer(), nullable=False),
        sa.Column("preferred_language", sa.String(16), nullable=False),
        sa.Column("target_date", sa.String(10)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("roadmap_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("weekly_minutes >= 30 AND weekly_minutes <= 2400", name="ck_career_goal_weekly_minutes"),
        sa.CheckConstraint("preferred_language IN ('telugu', 'english', 'mixed')", name="ck_career_goal_language"),
    )
    op.create_index("ix_career_goals_student_active", "career_goals", ["student_id", "active"])
    op.create_table(
        "student_skill_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_key", sa.String(64), nullable=False),
        sa.Column("proficiency", sa.String(24), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "skill_key", name="uq_student_skill_profile"),
        sa.CheckConstraint("proficiency IN ('unknown', 'beginner', 'intermediate', 'advanced')", name="ck_skill_profile_proficiency"),
    )
    op.create_table(
        "career_milestone_completions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_id", sa.String(120), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "goal_id", "milestone_id", name="uq_career_milestone_student_goal"),
    )
    op.create_index("ix_career_milestone_student_goal", "career_milestone_completions", ["student_id", "goal_id"])


def downgrade() -> None:
    op.drop_index("ix_career_milestone_student_goal", table_name="career_milestone_completions")
    op.drop_table("career_milestone_completions")
    op.drop_table("student_skill_profiles")
    op.drop_index("ix_career_goals_student_active", table_name="career_goals")
    op.drop_table("career_goals")
