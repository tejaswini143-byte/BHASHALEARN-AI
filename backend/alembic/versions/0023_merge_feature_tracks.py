"""Merge the independently developed feature migration heads."""

revision = "0023_merge_feature_tracks"
down_revision = (
    "0020_assistant_livekit_sessions",
    "0022_feature3_resume_profile",
    "0020_future_seeker_reflections",
    "0020_visual_lesson_session_state",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
