from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import Document, DocumentChunk, DocumentIndexGeneration, DocumentIndexState, DocumentPage, Student
from backend.app.services.document_index import IndexingError, index_document, search_documents
from backend.app.services.embeddings import EmbeddingError


class ControlledProvider:
    BATCH_SIZE = 16
    model = "gemini-embedding-001"
    dimensions = 768

    def __init__(self):
        self.calls = 0
        self.fail = False

    def embed_texts(self, texts, *, task_type):
        self.calls += 1
        assert task_type == "RETRIEVAL_DOCUMENT"
        if self.fail:
            raise EmbeddingError("simulated safe provider failure")
        return [[1.0] + [0.0] * 767 for _ in texts]


def add_document(db: Session, student_id: str, text: str, label: str) -> Document:
    document_id = str(uuid4())
    document = Document(
        id=document_id, student_id=student_id, original_filename=f"{label}.pdf", storage_key=f"{document_id}.pdf",
        mime_type="application/pdf", file_size_bytes=100, page_count=1, processing_status="processed",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.add(DocumentPage(document_id=document_id, page_number=1, extracted_text=text, character_count=len(text)))
    db.commit()
    return document


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'vectors.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def add_student(db: Session) -> Student:
    student = Student(id=str(uuid4()), email=f"{uuid4()}@test.invalid", display_name="ADV-02 test")
    db.add(student)
    db.commit()
    return student


def test_index_is_idempotent_and_reindex_replaces_generation_atomically(db):
    student = add_student(db)
    document = add_document(db, student.id, "తెలుగు learning basics", "lesson")
    provider = ControlledProvider()
    first = index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    first_generation = db.get(DocumentIndexState, document.id).active_generation_id
    assert first["status"] == "ready" and first["chunk_count"] == 1
    assert provider.calls == 1

    repeated = index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    assert repeated["chunk_count"] == 1
    assert provider.calls == 1
    assert db.scalar(select(func.count()).select_from(DocumentIndexGeneration).where(DocumentIndexGeneration.document_id == document.id)) == 1

    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == document.id))
    page.extracted_text = "Updated తెలుగు learning content"
    db.commit()
    replaced = index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    second_generation = db.get(DocumentIndexState, document.id).active_generation_id
    assert replaced["status"] == "ready"
    assert second_generation != first_generation
    assert db.get(DocumentIndexGeneration, first_generation) is None
    assert db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.generation_id == second_generation)) == 1


def test_failed_reindex_preserves_old_active_generation_and_retry_works(db):
    student = add_student(db)
    document = add_document(db, student.id, "stable text for search", "stable")
    provider = ControlledProvider()
    index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    state = db.get(DocumentIndexState, document.id)
    active_id = state.active_generation_id
    provider.fail = True
    with pytest.raises(IndexingError) as error:
        index_document(db, document_id=document.id, student_id=student.id, provider=provider, force=True)
    assert error.value.status_code == 502
    state = db.get(DocumentIndexState, document.id)
    assert state.status == "failed" and state.active_generation_id == active_id
    results = search_documents(db, student_id=student.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=5)
    assert len(results) == 1 and results[0]["document_id"] == document.id

    provider.fail = False
    index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    assert db.get(DocumentIndexState, document.id).status == "ready"


def test_search_filters_student_and_stable_cosine_ranking(db):
    owner = add_student(db)
    other = add_student(db)
    own_document = add_document(db, owner.id, "owner private learning text", "own")
    foreign_document = add_document(db, other.id, "foreign private learning text", "foreign")
    provider = ControlledProvider()
    index_document(db, document_id=own_document.id, student_id=owner.id, provider=provider)
    index_document(db, document_id=foreign_document.id, student_id=other.id, provider=provider)
    own = search_documents(db, student_id=owner.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=5)
    foreign = search_documents(db, student_id=other.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=5)
    assert [item["document_id"] for item in own] == [own_document.id]
    assert [item["document_id"] for item in foreign] == [foreign_document.id]
    assert own[0]["score"] == pytest.approx(1.0)


def test_search_can_be_restricted_to_selected_student_documents(db):
    student = add_student(db)
    first = add_document(db, student.id, "first selected lesson", "first")
    second = add_document(db, student.id, "second unselected lesson", "second")
    provider = ControlledProvider()
    index_document(db, document_id=first.id, student_id=student.id, provider=provider)
    index_document(db, document_id=second.id, student_id=student.id, provider=provider)
    results = search_documents(db, student_id=student.id, query_vector=[1.0] + [0.0] * 767,
                               model=provider.model, top_k=5, document_ids=[first.id])
    assert [item["document_id"] for item in results] == [first.id]


def test_partial_batch_failure_writes_no_visible_chunks(db):
    student = add_student(db)
    document = add_document(db, student.id, "one two three four five six seven eight nine ten", "partial")

    class FailingAfterFirst(ControlledProvider):
        BATCH_SIZE = 1

        def embed_texts(self, texts, *, task_type):
            self.calls += 1
            if self.calls > 1:
                raise EmbeddingError("simulated partial batch failure")
            return [[1.0] + [0.0] * 767]

    provider = FailingAfterFirst()
    with pytest.raises(IndexingError):
        index_document(db, document_id=document.id, student_id=student.id, provider=provider, chunk_size=10, overlap=2)
    state = db.get(DocumentIndexState, document.id)
    assert state.status == "failed" and state.active_generation_id is None
    assert db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == document.id)) == 0


def test_interrupted_processing_can_be_retried_after_heartbeat_stales(db):
    student = add_student(db)
    document = add_document(db, student.id, "retry after interrupted worker", "stale")
    generation = DocumentIndexGeneration(
        id=str(uuid4()), document_id=document.id, student_id=student.id, status="building",
        embedding_model="gemini-embedding-001", embedding_dimensions=768, chunking_version="page-char-v1",
        source_hash="0" * 64, created_at=datetime.now(timezone.utc) - timedelta(minutes=12),
    )
    state = DocumentIndexState(
        document_id=document.id, student_id=student.id, status="processing", active_generation_id=None,
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=12),
    )
    db.add(generation)
    db.add(state)
    db.commit()
    result = index_document(db, document_id=document.id, student_id=student.id, provider=ControlledProvider())
    assert result["status"] == "ready"
    assert db.get(DocumentIndexGeneration, generation.id).status == "failed"


def test_wrong_embedding_dimension_fails_before_indexing(db):
    student = add_student(db)
    document = add_document(db, student.id, "a valid page", "wrong-dimension")
    provider = ControlledProvider()
    provider.dimensions = 767
    with pytest.raises(IndexingError) as error:
        index_document(db, document_id=document.id, student_id=student.id, provider=provider)
    assert error.value.code == "embedding_configuration_mismatch"
    assert db.get(DocumentIndexState, document.id) is None
