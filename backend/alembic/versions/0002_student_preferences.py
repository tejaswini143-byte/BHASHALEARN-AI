"""Add student learning preferences.

Revision ID: 0002_student_preferences
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_student_preferences"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_preferences",
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("preferred_language", sa.String(16), nullable=False, server_default="mixed"),
        sa.Column("learning_level", sa.String(16), nullable=False, server_default="beginner"),
        sa.Column("learning_goal", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("student_preferences")
