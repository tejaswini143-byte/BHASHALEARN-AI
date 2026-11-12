"""Persist selectable local deadline-call duration."""
from alembic import op
import sqlalchemy as sa

revision = "0018_local_call_duration"
down_revision = "0017_local_deadline_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assistant_settings", sa.Column("max_call_duration_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("assistant_local_calls", sa.Column("max_duration_minutes", sa.Integer(), nullable=False, server_default="30"))


def downgrade() -> None:
    op.drop_column("assistant_local_calls", "max_duration_minutes")
    op.drop_column("assistant_settings", "max_call_duration_minutes")
