"""Create learning memories table."""
from alembic import op
import sqlalchemy as sa

revision = "0004_learning_memories"
down_revision = "0003_lessons"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("learning_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_learning_memories_student_id", "learning_memories", ["student_id"])

def downgrade():
    op.drop_index("ix_learning_memories_student_id", table_name="learning_memories")
    op.drop_table("learning_memories")
