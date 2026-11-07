"""Real PostgreSQL/pgvector integration tests. Require the exact disposable ADV-02 DB URL."""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.documents import get_embedding_provider
from backend.app.config import get_settings
from backend.app.db.models import Document, DocumentChunk, DocumentIndexGeneration, DocumentIndexState, DocumentPage, Student
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.document_index import IndexingError, index_document, search_documents
from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider


class ControlledProvider:
    BATCH_SIZE = 16
    model = "gemini-embedding-001"
    dimensions = 768

    def __init__(self, *, fail=False, started=None, release=None):
        self.fail = fail
        self.started = started
        self.release = release
        self.calls = 0

    def embed_texts(self, texts, *, task_type):
        self.calls += 1
        if self.started:
            self.started.set()
        if self.release:
            self.release.wait(10)
        if self.fail:
            raise EmbeddingError("simulated provider failure")
        axis = 1.0 if task_type == "RETRIEVAL_QUERY" else 1.0
        return [[axis] + [0.0] * 767 for _ in texts]


@pytest.fixture
def pg_context():
    value = os.getenv("BHASHALEARN_ADV02_TEST_DATABASE_URL")
    if not value:
        pytest.skip("Set BHASHALEARN_ADV02_TEST_DATABASE_URL to the dedicated ADV-02 test database.")
    url = make_url(value)
    if url.database != "bhashalearn_adv02_test" or url.username != "bhashalearn_adv02":
        raise RuntimeError("PostgreSQL integration tests refuse any database/role other than the dedicated ADV-02 target.")
    engine = create_engine(value, pool_pre_ping=True)
    with engine.connect() as connection:
        identity = connection.execute(text("SELECT current_database(), current_user")).one()
        extension = connection.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).scalar_one_or_none()
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
        if identity != ("bhashalearn_adv02_test", "bhashalearn_adv02") or extension != "0.8.7" or revision != "0008_document_embeddings":
            engine.dispose()
            raise RuntimeError("PostgreSQL integration identity, extension, or migration-head check failed before test writes.")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    created_students: list[str] = []
    yield engine, factory, created_students
    if created_students:
        with factory() as cleanup:
            cleanup.execute(delete(Student).where(Student.id.in_(created_students)))
            cleanup.commit()
    engine.dispose()


def seed_student(db: Session, created: list[str]) -> Student:
    student = Student(id=str(uuid4()), email=f"{uuid4()}@adv02.invalid", display_name="ADV-02 isolated test")
    db.add(student)
    db.commit()
    created.append(student.id)
    return student


def seed_document(db: Session, student_id: str, text_value: str) -> Document:
    document_id = str(uuid4())
    document = Document(
        id=document_id, student_id=student_id, original_filename="isolated-fixture.pdf",
        storage_key=f"{document_id}.pdf", mime_type="application/pdf", file_size_bytes=100,
        page_count=1, processing_status="processed", created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(document)
    db.add(DocumentPage(document_id=document_id, page_number=1, extracted_text=text_value, character_count=len(text_value)))
    db.commit()
    return document


def access_token(student_id: str, secret: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": student_id, "iat": now, "exp": now + timedelta(minutes=5), "type": "access"}, secret, algorithm="HS256")


def test_postgres_idempotency_reindex_failure_and_owner_scoped_authenticated_search(pg_context, monkeypatch):
    _, factory, created = pg_context
    with factory() as db:
        owner = seed_student(db, created)
        stranger = seed_student(db, created)
        own_doc = seed_document(db, owner.id, "private algebra lesson in Telugu")
        foreign_doc = seed_document(db, stranger.id, "private algebra lesson from another student")
        provider = ControlledProvider()
        result = index_document(db, document_id=own_doc.id, student_id=owner.id, provider=provider)
        active_id = db.get(DocumentIndexState, own_doc.id).active_generation_id
        assert result["status"] == "ready"
        same = index_document(db, document_id=own_doc.id, student_id=owner.id, provider=provider)
        assert same["chunk_count"] == result["chunk_count"] and provider.calls == 1
        index_document(db, document_id=foreign_doc.id, student_id=stranger.id, provider=provider)

        page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == own_doc.id))
        page.extracted_text = "private updated algebra in Telugu"
        db.commit()
        index_document(db, document_id=own_doc.id, student_id=owner.id, provider=provider)
        replacement_id = db.get(DocumentIndexState, own_doc.id).active_generation_id
        assert replacement_id != active_id
        assert db.get(DocumentIndexGeneration, active_id) is None

        failing = ControlledProvider(fail=True)
        with pytest.raises(IndexingError):
            index_document(db, document_id=own_doc.id, student_id=owner.id, provider=failing, force=True)
        state = db.get(DocumentIndexState, own_doc.id)
        assert state.status == "failed" and state.active_generation_id == replacement_id
        owned = search_documents(db, student_id=owner.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=10)
        foreign = search_documents(db, student_id=stranger.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=10)
        assert {item["document_id"] for item in owned} == {own_doc.id}
        assert {item["document_id"] for item in foreign} == {foreign_doc.id}

        secret = "isolated-adv02-test-secret-only-32-bytes"
        monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", secret)
        get_settings.cache_clear()
        app = create_app()

        def override_db():
            with factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_embedding_provider] = lambda: ControlledProvider()
        try:
            with TestClient(app) as client:
                headers = {"Authorization": f"Bearer {access_token(owner.id, secret)}"}
                response = client.post("/api/v1/documents/search", headers=headers, json={"query": "algebra", "top_k": 5})
                assert response.status_code == 200
                assert {item["document_id"] for item in response.json()["items"]} == {own_doc.id}
                forbidden = client.get(f"/api/v1/documents/{foreign_doc.id}/index-status", headers=headers)
                assert forbidden.status_code == 404
                assert client.post("/api/v1/documents/search", headers=headers, json={"query": "  ", "top_k": 2}).status_code == 422
                assert client.post("/api/v1/documents/search", headers=headers, json={"query": "x", "top_k": 21}).status_code == 422
                assert client.post("/api/v1/documents/search", headers=headers, json={"query": "x" * 1001}).status_code == 422
                app.dependency_overrides[get_embedding_provider] = lambda: GeminiEmbeddingProvider(api_key="")
                unavailable = client.post(f"/api/v1/documents/{own_doc.id}/index", headers=headers)
                assert unavailable.status_code == 503
                app.dependency_overrides[get_embedding_provider] = lambda: ControlledProvider()
                indexed = client.post(f"/api/v1/documents/{own_doc.id}/index", headers=headers)
                assert indexed.status_code == 200 and indexed.json()["status"] == "ready"
                assert client.get(f"/api/v1/documents/{own_doc.id}/index-status", headers=headers).json()["status"] == "ready"
        finally:
            app.dependency_overrides.clear()
            get_settings.cache_clear()

        db.delete(own_doc)
        db.commit()
        assert db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.document_id == own_doc.id)) == 0
        assert db.scalar(select(func.count()).select_from(DocumentIndexState).where(DocumentIndexState.document_id == own_doc.id)) == 0
        assert search_documents(db, student_id=owner.id, query_vector=[1.0] + [0.0] * 767, model=provider.model, top_k=5) == []


def test_postgres_concurrent_indexing_attempt_is_rejected(pg_context):
    _, factory, created = pg_context
    with factory() as db:
        owner = seed_student(db, created)
        document = seed_document(db, owner.id, "concurrent indexing fixture text")

    started, release = Event(), Event()
    first_provider = ControlledProvider(started=started, release=release)
    with ThreadPoolExecutor(max_workers=2) as executor:
        def first_attempt():
            with factory() as session:
                return index_document(session, document_id=document.id, student_id=owner.id, provider=first_provider)

        first = executor.submit(first_attempt)
        assert started.wait(5), "first provider call did not begin"
        try:
            with factory() as second_session:
                with pytest.raises(IndexingError) as error:
                    index_document(second_session, document_id=document.id, student_id=owner.id, provider=ControlledProvider())
                assert error.value.status_code == 409
        finally:
            release.set()
        assert first.result(timeout=10)["status"] == "ready"
