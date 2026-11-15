"""Persist reviewable Gemini resume extraction candidates on career goals."""
from alembic import op
import sqlalchemy as sa

revision = "0022_feature3_resume_profile"
down_revision = "0021_feature3_experience_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_goals", sa.Column("resume_profile_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("career_goals", "resume_profile_json")
