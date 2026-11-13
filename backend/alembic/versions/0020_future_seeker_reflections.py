"""Add student-owned Future Seeker illustrative reflections.

Revision ID: 0020_future_seeker_reflections
Revises: 0019_explicit_call_microphone_auth
"""
from alembic import op
import sqlalchemy as sa

revision = "0020_future_seeker_reflections"
down_revision = "0019_explicit_call_microphone_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "future_seeker_reflections",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("student_id", sa.String(length=36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("career_id", sa.String(length=40), nullable=False),
        sa.Column("completed_steps", sa.Integer(), nullable=False),
        sa.Column("observed_skills_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_future_seeker_owner_created",
        "future_seeker_reflections",
        ["student_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_future_seeker_owner_created", table_name="future_seeker_reflections")
    op.drop_table("future_seeker_reflections")
