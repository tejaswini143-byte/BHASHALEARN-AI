"""Store a student's self-selected learning pace after ADV-02 embeddings."""
from alembic import op
import sqlalchemy as sa

revision = "0009_learning_pace"
down_revision = "0008_document_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_preferences",
        sa.Column("learning_pace", sa.String(16), nullable=False, server_default="steady"),
    )


def downgrade() -> None:
    op.drop_column("student_preferences", "learning_pace")
