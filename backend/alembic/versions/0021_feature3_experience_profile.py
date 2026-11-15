"""Store optional student experience context for Future Seeker."""
from alembic import op
import sqlalchemy as sa

revision = "0021_feature3_experience_profile"
down_revision = "0020_feature3_future_seeker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("career_goals", sa.Column("experience_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("career_goals", "experience_summary")
