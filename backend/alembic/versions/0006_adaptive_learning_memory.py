"""Add evidence-backed adaptive learning and assessment attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0006_adaptive_learning_memory"
down_revision = "0005_session_visual_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("learning_progress", sa.Column("normalized_topic_key", sa.String(200), nullable=True))
    op.add_column("learning_progress", sa.Column("evidence_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("correct_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("incorrect_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("ambiguous_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("evidence_status", sa.String(24), nullable=False, server_default="unassessed"))
    op.add_column("learning_progress", sa.Column("last_assessed_at", sa.DateTime(timezone=True), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, topic FROM learning_progress")).mappings().all()
    for row in rows:
        key = " ".join((row["topic"] or "").strip().lower().split())[:200]
        bind.execute(
            sa.text("UPDATE learning_progress SET normalized_topic_key=:key, evidence_status='legacy_unvalidated' WHERE id=:id"),
            {"key": key, "id": row["id"]},
        )
    with op.batch_alter_table("learning_progress") as batch:
        batch.alter_column("normalized_topic_key", existing_type=sa.String(200), nullable=False)
    op.create_index("ix_learning_progress_normalized_topic_key", "learning_progress", ["normalized_topic_key"])
    op.create_table(
        "learning_assessment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("normalized_topic_key", sa.String(200), nullable=False),
        sa.Column("question_id", sa.String(100), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("submitted_answer", sa.String(500), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("student_id", "idempotency_key", name="uq_assessment_student_idempotency"),
    )
    op.create_index("ix_learning_assessment_attempts_student_id", "learning_assessment_attempts", ["student_id"])
    op.create_index("ix_learning_assessment_attempts_session_id", "learning_assessment_attempts", ["session_id"])
    op.create_index("ix_learning_assessment_attempts_normalized_topic_key", "learning_assessment_attempts", ["normalized_topic_key"])


def downgrade() -> None:
    op.drop_index("ix_learning_assessment_attempts_normalized_topic_key", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_session_id", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_student_id", table_name="learning_assessment_attempts")
    op.drop_table("learning_assessment_attempts")
    op.drop_index("ix_learning_progress_normalized_topic_key", table_name="learning_progress")
    op.drop_column("learning_progress", "last_assessed_at")
    op.drop_column("learning_progress", "evidence_status")
    op.drop_column("learning_progress", "ambiguous_attempts")
    op.drop_column("learning_progress", "incorrect_attempts")
    op.drop_column("learning_progress", "correct_attempts")
    op.drop_column("learning_progress", "evidence_attempts")
    op.drop_column("learning_progress", "normalized_topic_key")
