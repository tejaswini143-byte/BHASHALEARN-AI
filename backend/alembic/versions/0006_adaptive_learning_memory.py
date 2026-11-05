"""Add validated, student-owned learning evidence and mastery fields."""
from collections import defaultdict
import re
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = "0006_adaptive_learning_memory"
down_revision = "0005_session_visual_state"
branch_labels = None
depends_on = None


def _topic_key(topic: str) -> str:
    normalized = unicodedata.normalize("NFKC", " ".join(topic.split())).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def upgrade() -> None:
    op.add_column("learning_progress", sa.Column("topic_key", sa.String(600), nullable=True))
    op.add_column("learning_progress", sa.Column("evidence_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("correct_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("incorrect_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("learning_progress", sa.Column("correct_streak", sa.Integer(), nullable=False, server_default="0"))

    bind = op.get_bind()
    op.create_table(
        "learning_progress_legacy_duplicates",
        sa.Column("legacy_progress_id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    legacy_duplicates = sa.table(
        "learning_progress_legacy_duplicates",
        sa.column("legacy_progress_id", sa.String(36)),
        sa.column("student_id", sa.String(36)),
        sa.column("topic", sa.String(200)),
        sa.column("mastery_score", sa.Float()),
        sa.column("attempts", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    progress = sa.table(
        "learning_progress",
        sa.column("id", sa.String(36)),
        sa.column("student_id", sa.String(36)),
        sa.column("topic", sa.String(200)),
        sa.column("topic_key", sa.String(600)),
        sa.column("mastery_score", sa.Float()),
        sa.column("attempts", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(sa.select(
        progress.c.id, progress.c.student_id, progress.c.topic,
        progress.c.mastery_score, progress.c.attempts, progress.c.updated_at,
    )).mappings().all()
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(row["student_id"], _topic_key(row["topic"]))].append(dict(row))

    # Earlier progress accepted caller-provided display casing. Collapse equivalent
    # legacy rows conservatively, retaining the highest score and largest attempt
    # count while marking all of them as unverified evidence (evidence_count=0).
    for (_, key), group in groups.items():
        group.sort(key=lambda item: item["id"])
        keeper = group[0]
        bind.execute(progress.update().where(progress.c.id == keeper["id"]).values(
            topic_key=key,
            mastery_score=max(float(item["mastery_score"]) for item in group),
            attempts=max(int(item["attempts"]) for item in group),
            updated_at=max(item["updated_at"] for item in group),
        ))
        duplicate_ids = [item["id"] for item in group[1:]]
        if duplicate_ids:
            bind.execute(legacy_duplicates.insert(), [
                {
                    "legacy_progress_id": item["id"],
                    "student_id": item["student_id"],
                    "topic": item["topic"],
                    "mastery_score": item["mastery_score"],
                    "attempts": item["attempts"],
                    "updated_at": item["updated_at"],
                }
                for item in group[1:]
            ])
            bind.execute(progress.delete().where(progress.c.id.in_(duplicate_ids)))

    with op.batch_alter_table("learning_progress") as batch:
        batch.alter_column("topic_key", existing_type=sa.String(600), nullable=False)
        batch.create_unique_constraint("uq_progress_student_topic_key", ["student_id", "topic_key"])
        batch.create_check_constraint("ck_progress_mastery_bounds", "mastery_score >= 0 AND mastery_score <= 100")

    op.create_table(
        "learning_assessment_attempts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("learning_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("progress_id", sa.String(36), sa.ForeignKey("learning_progress.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(200), nullable=False),
        sa.Column("topic_key", sa.String(600), nullable=False),
        sa.Column("language", sa.String(16), nullable=False),
        sa.Column("question_code", sa.String(120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("choices", sa.JSON(), nullable=False),
        sa.Column("expected_answer", sa.String(8), nullable=False),
        sa.Column("misconception_map", sa.JSON(), nullable=False),
        sa.Column("submitted_answer", sa.String(16)),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("misconception_code", sa.String(100)),
        sa.Column("feedback", sa.Text()),
        sa.Column("result_mastery_score", sa.Float()),
        sa.Column("result_evidence_count", sa.Integer()),
        sa.Column("result_category", sa.String(40)),
        sa.Column("result_difficulty", sa.String(24)),
        sa.Column("result_strategy", sa.String(48)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_learning_assessment_attempts_student_id", "learning_assessment_attempts", ["student_id"])
    op.create_index("ix_learning_assessment_attempts_session_id", "learning_assessment_attempts", ["session_id"])
    op.create_index("ix_learning_assessment_attempts_progress_id", "learning_assessment_attempts", ["progress_id"])
    op.create_index("ix_learning_assessment_attempts_topic_key", "learning_assessment_attempts", ["topic_key"])
    op.create_index(
        "ix_learning_assessment_topic_recent",
        "learning_assessment_attempts",
        ["student_id", "topic_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_learning_assessment_topic_recent", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_topic_key", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_progress_id", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_session_id", table_name="learning_assessment_attempts")
    op.drop_index("ix_learning_assessment_attempts_student_id", table_name="learning_assessment_attempts")
    op.drop_table("learning_assessment_attempts")
    with op.batch_alter_table("learning_progress") as batch:
        batch.drop_constraint("ck_progress_mastery_bounds", type_="check")
        batch.drop_constraint("uq_progress_student_topic_key", type_="unique")
        batch.drop_column("correct_streak")
        batch.drop_column("incorrect_attempts")
        batch.drop_column("correct_attempts")
        batch.drop_column("evidence_count")
        batch.drop_column("topic_key")
    bind = op.get_bind()
    archive = sa.table(
        "learning_progress_legacy_duplicates",
        sa.column("legacy_progress_id", sa.String(36)),
        sa.column("student_id", sa.String(36)),
        sa.column("topic", sa.String(200)),
        sa.column("mastery_score", sa.Float()),
        sa.column("attempts", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    progress = sa.table(
        "learning_progress",
        sa.column("id", sa.String(36)),
        sa.column("student_id", sa.String(36)),
        sa.column("topic", sa.String(200)),
        sa.column("mastery_score", sa.Float()),
        sa.column("attempts", sa.Integer()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(sa.select(archive)).mappings().all()
    if rows:
        bind.execute(progress.insert(), [
            {
                "id": row["legacy_progress_id"],
                "student_id": row["student_id"],
                "topic": row["topic"],
                "mastery_score": row["mastery_score"],
                "attempts": row["attempts"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ])
    op.drop_table("learning_progress_legacy_duplicates")
