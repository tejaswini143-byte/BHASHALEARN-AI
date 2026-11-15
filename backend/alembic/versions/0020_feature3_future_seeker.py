"""Personalize Future Seeker profiles and retain roadmap revisions."""
from alembic import op
import sqlalchemy as sa

revision = "0020_feature3_future_seeker"
down_revision = "0019_explicit_call_microphone_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_goals", sa.Column("field_of_study", sa.String(120), nullable=True))
    op.add_column("career_goals", sa.Column("daily_minutes", sa.Integer(), nullable=False, server_default="120"))
    op.add_column("career_goals", sa.Column("study_days_per_week", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("career_goals", sa.Column("learning_format", sa.String(24), nullable=False, server_default="mixed"))
    op.add_column("career_goals", sa.Column("timeframe_weeks", sa.Integer(), nullable=True))
    op.add_column("career_goals", sa.Column("constraints_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("career_goals", sa.Column("analysis_json", sa.Text(), nullable=True))
    op.create_table(
        "career_roadmap_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("roadmap_json", sa.Text(), nullable=False),
        sa.Column("change_reason", sa.String(64), nullable=False, server_default="generated"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "goal_id", "version_number", name="uq_career_roadmap_version_owner_goal"),
    )
    op.create_index("ix_career_roadmap_versions_owner_goal", "career_roadmap_versions",
                    ["student_id", "goal_id", "version_number"])
    op.create_table(
        "career_saved_resources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", sa.String(36), sa.ForeignKey("career_goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_url", sa.String(2048), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(80), nullable=False),
        sa.Column("free", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("student_id", "goal_id", "resource_url", name="uq_career_saved_resource_owner_goal_url"),
    )
    op.create_index("ix_career_saved_resources_owner_goal", "career_saved_resources", ["student_id", "goal_id"])


def downgrade() -> None:
    op.drop_index("ix_career_saved_resources_owner_goal", table_name="career_saved_resources")
    op.drop_table("career_saved_resources")
    op.drop_index("ix_career_roadmap_versions_owner_goal", table_name="career_roadmap_versions")
    op.drop_table("career_roadmap_versions")
    for column in ("analysis_json", "constraints_json", "timeframe_weeks", "learning_format",
                   "study_days_per_week", "daily_minutes", "field_of_study"):
        op.drop_column("career_goals", column)
