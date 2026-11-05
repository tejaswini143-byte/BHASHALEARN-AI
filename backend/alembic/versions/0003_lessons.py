"""Add ordered lessons for courses.

Revision ID: 0003_lessons
Revises: 0002_student_preferences
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_lessons"
down_revision = "0002_student_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lessons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("course_id", "position", name="uq_lesson_course_position"),
    )
    op.create_index("ix_lessons_course_id", "lessons", ["course_id"])


def downgrade() -> None:
    op.drop_index("ix_lessons_course_id", table_name="lessons")
    op.drop_table("lessons")
