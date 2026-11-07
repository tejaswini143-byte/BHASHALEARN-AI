"""Add student-scoped, versioned document embeddings."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0008_document_embeddings"
down_revision = "0007_private_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        extension = bind.execute(sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).scalar_one_or_none()
        if extension is None:
            raise RuntimeError("The pgvector extension must already be enabled in this database")
    op.create_index("uq_documents_id_student_id", "documents", ["id", "student_id"], unique=True)
    op.create_table(
        "document_index_generations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("embedding_model", sa.String(80), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("chunking_version", sa.String(40), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id", "student_id"], ["documents.id", "documents.student_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("id", "document_id", "student_id", name="uq_document_index_generation_owner"),
        sa.CheckConstraint("status IN ('building', 'ready', 'failed')", name="ck_document_index_generation_status"),
        sa.CheckConstraint("embedding_dimensions = 768", name="ck_document_index_generation_dimensions"),
    )
    op.create_index("ix_document_index_generations_owner_status", "document_index_generations", ["student_id", "status"])
    op.create_table(
        "document_index_states",
        sa.Column("document_id", sa.String(36), primary_key=True),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("active_generation_id", sa.String(36), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id", "student_id"], ["documents.id", "documents.student_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["active_generation_id", "document_id", "student_id"],
            ["document_index_generations.id", "document_index_generations.document_id", "document_index_generations.student_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("status IN ('pending', 'processing', 'ready', 'failed')", name="ck_document_index_state_status"),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("generation_id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("embedding_model", sa.String(80), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id", "document_id", "student_id"],
            ["document_index_generations.id", "document_index_generations.document_id", "document_index_generations.student_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("generation_id", "ordinal", name="uq_document_chunks_generation_ordinal"),
        sa.CheckConstraint("page_number >= 1", name="ck_document_chunks_page_positive"),
        sa.CheckConstraint("ordinal >= 0", name="ck_document_chunks_ordinal_nonnegative"),
        sa.CheckConstraint("char_count > 0", name="ck_document_chunks_char_count_positive"),
        sa.CheckConstraint("embedding_dimensions = 768", name="ck_document_chunks_embedding_dimensions"),
    )
    op.create_index("ix_document_chunks_owner_document", "document_chunks", ["student_id", "document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_owner_document", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("document_index_states")
    op.drop_index("ix_document_index_generations_owner_status", table_name="document_index_generations")
    op.drop_table("document_index_generations")
    op.drop_index("uq_documents_id_student_id", table_name="documents")
