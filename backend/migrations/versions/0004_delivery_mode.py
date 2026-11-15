"""Add per-deadline reminder delivery mode."""
from alembic import op
import sqlalchemy as sa

revision = "0004_delivery_mode"
down_revision = "0003_outbound_call_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deadlines", sa.Column("delivery_mode", sa.String(16), nullable=False, server_default="browser"))


def downgrade() -> None:
    op.drop_column("deadlines", "delivery_mode")
