"""Require an explicit one-use authorization for each call microphone turn."""
from alembic import op
import sqlalchemy as sa

revision = "0019_explicit_call_microphone_auth"
down_revision = "0018_local_call_duration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assistant_local_calls", sa.Column("mic_authorization_hash", sa.String(64), nullable=True))
    op.add_column("assistant_local_calls", sa.Column("mic_authorization_expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("assistant_local_calls", "mic_authorization_expires_at")
    op.drop_column("assistant_local_calls", "mic_authorization_hash")
