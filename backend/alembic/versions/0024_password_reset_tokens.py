"""Store hashed, expiring password reset tokens."""
from alembic import op
import sqlalchemy as sa

revision = "0024_password_reset_tokens"
down_revision = "0023_merge_feature_tracks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_student_id", "password_reset_tokens", ["student_id"])


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_student_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
