"""Persist student enrollments and in-app course lesson completion."""
from alembic import op
import sqlalchemy as sa

revision = "0016_course_learning_paths"
down_revision = "0015_int17_provider_integrations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("student_course_progress"):
        return
    op.create_table(
        "student_course_progress",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_key", sa.String(length=80), nullable=False),
        sa.Column("completed_lesson_ids", sa.JSON(), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "course_key", name="uq_student_course_progress_owner_course"),
    )
    op.create_index("ix_student_course_progress_student_id", "student_course_progress", ["student_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("student_course_progress"):
        return
    op.drop_index("ix_student_course_progress_student_id", table_name="student_course_progress")
    op.drop_table("student_course_progress")
