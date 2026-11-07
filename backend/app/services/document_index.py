"""Transactional, student-owned document indexing and exact vector retrieval."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    Document,
    DocumentChunk,
    DocumentIndexGeneration,
    DocumentIndexState,
    DocumentPage,
)
from backend.app.services.chunking import CHUNKING_VERSION, chunk_pages
from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider


class IndexingError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _source_hash(pages: list[tuple[int, str]], model: str, dimensions: int, chunk_size: int, overlap: int) -> str:
    canonical = json.dumps(
        {"pages": pages, "model": model, "dimensions": dimensions, "chunking": CHUNKING_VERSION, "size": chunk_size, "overlap": overlap},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _status_result(db: Session, document: Document, state: DocumentIndexState | None) -> dict:
    generation = db.get(DocumentIndexGeneration, state.active_generation_id) if state and state.active_generation_id else None
    chunks = 0
    if generation is not None:
        chunks = db.scalar(select(func.count()).select_from(DocumentChunk).where(DocumentChunk.generation_id == generation.id)) or 0
    return {
        "document_id": document.id,
        "status": state.status if state else "pending",
        "error_code": state.error_code if state else None,
        "chunk_count": chunks,
        "embedding_model": generation.embedding_model if generation else None,
        "embedding_dimensions": generation.embedding_dimensions if generation else None,
        "updated_at": state.updated_at if state else document.updated_at,
    }


def index_document(
    db: Session,
    *,
    document_id: str,
    student_id: str,
    provider: GeminiEmbeddingProvider,
    force: bool = False,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> dict:
    """Build a replacement generation off-line, then switch it atomically."""
    if provider.dimensions != 768:
        raise IndexingError("embedding_configuration_mismatch", "Embedding configuration does not match vector storage.", 503)
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.student_id == student_id).with_for_update()
    )
    if document is None:
        raise IndexingError("document_not_found", "Document not found", 404)
    if document.processing_status != "processed":
        state = db.get(DocumentIndexState, document.id)
        if state is None:
            state = DocumentIndexState(document_id=document.id, student_id=student_id, status="failed", error_code="NO_USABLE_TEXT")
            db.add(state)
        else:
            state.status = "failed"
            state.error_code = "NO_USABLE_TEXT"
            state.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise IndexingError("document_text_unavailable", "This document has no usable extracted text.", 422)
    pages = [(page.page_number, page.extracted_text) for page in db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == document.id).order_by(DocumentPage.page_number)
    ).all()]
    source_hash = _source_hash(pages, provider.model, provider.dimensions, chunk_size, overlap)
    state = db.get(DocumentIndexState, document.id)
    if state and state.status == "processing":
        updated = state.updated_at
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - updated < timedelta(minutes=10):
            raise IndexingError("indexing_in_progress", "Document indexing is already in progress.", 409)
        abandoned = db.scalar(select(DocumentIndexGeneration).where(
            DocumentIndexGeneration.document_id == document.id,
            DocumentIndexGeneration.student_id == student_id,
            DocumentIndexGeneration.status == "building",
        ))
        if abandoned:
            abandoned.status = "failed"
        state.status = "failed"
        state.error_code = "INDEXING_INTERRUPTED"
        db.commit()
    if state and state.status == "ready" and state.active_generation_id and not force:
        active = db.get(DocumentIndexGeneration, state.active_generation_id)
        if active and active.status == "ready" and active.source_hash == source_hash:
            return _status_result(db, document, state)

    chunks = chunk_pages(document.id, pages, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        if state is None:
            state = DocumentIndexState(document_id=document.id, student_id=student_id, status="failed", error_code="NO_USABLE_TEXT")
            db.add(state)
        else:
            state.status = "failed"
            state.error_code = "NO_USABLE_TEXT"
            state.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise IndexingError("document_text_unavailable", "This document has no usable extracted text.", 422)

    generation = DocumentIndexGeneration(
        id=str(uuid4()), document_id=document.id, student_id=student_id, status="building",
        embedding_model=provider.model, embedding_dimensions=provider.dimensions,
        chunking_version=CHUNKING_VERSION, source_hash=source_hash,
    )
    if state is None:
        state = DocumentIndexState(document_id=document.id, student_id=student_id, status="processing")
        db.add(state)
    else:
        state.status = "processing"
        state.error_code = None
        state.updated_at = datetime.now(timezone.utc)
    db.add(generation)
    db.commit()
    previous_generation_id = state.active_generation_id
    try:
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), provider.BATCH_SIZE):
            vectors.extend(provider.embed_texts([chunk.content for chunk in chunks[start : start + provider.BATCH_SIZE]], task_type="RETRIEVAL_DOCUMENT"))
            state.updated_at = datetime.now(timezone.utc)
            db.commit()
        if len(vectors) != len(chunks):
            raise EmbeddingError("Gemini embedding provider returned an invalid response")
        if any(len(vector) != 768 or not all(math.isfinite(value) for value in vector) for vector in vectors):
            raise EmbeddingError("Gemini embedding provider returned an invalid vector")
        for chunk, vector in zip(chunks, vectors, strict=True):
            db.add(DocumentChunk(
                id=chunk.id, generation_id=generation.id, document_id=document.id, student_id=student_id,
                page_number=chunk.page_number, ordinal=chunk.ordinal, content=chunk.content,
                content_hash=chunk.content_hash, char_count=len(chunk.content), embedding_model=provider.model,
                embedding_dimensions=provider.dimensions, embedding=vector,
            ))
        db.flush()
        generation.status = "ready"
        generation.ready_at = datetime.now(timezone.utc)
        state.active_generation_id = generation.id
        state.status = "ready"
        state.error_code = None
        state.updated_at = datetime.now(timezone.utc)
        if previous_generation_id and previous_generation_id != generation.id:
            previous = db.get(DocumentIndexGeneration, previous_generation_id)
            if previous:
                db.delete(previous)
        db.commit()
    except Exception as exc:
        db.rollback()
        state = db.get(DocumentIndexState, document.id)
        generation = db.get(DocumentIndexGeneration, generation.id)
        if state is not None:
            state.status = "failed"
            state.error_code = "EMBEDDING_FAILED"
            state.updated_at = datetime.now(timezone.utc)
        if generation is not None:
            generation.status = "failed"
        db.commit()
        if isinstance(exc, EmbeddingError):
            raise IndexingError("embedding_failed", str(exc), exc.status_code) from None
        raise
    state = db.get(DocumentIndexState, document.id)
    document = db.get(Document, document.id)
    return _status_result(db, document, state)


def index_status(db: Session, *, document_id: str, student_id: str) -> dict:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.student_id == student_id))
    if document is None:
        raise IndexingError("document_not_found", "Document not found", 404)
    state = db.get(DocumentIndexState, document.id)
    return _status_result(db, document, state)


def search_documents(
    db: Session,
    *,
    student_id: str,
    query_vector: list[float],
    model: str,
    top_k: int,
) -> list[dict]:
    """Search only active generations owned by the authenticated student."""
    from backend.app.db.models import Document

    statement = (
        select(DocumentChunk, Document.original_filename)
        .join(DocumentIndexState, DocumentIndexState.document_id == DocumentChunk.document_id)
        .join(DocumentIndexGeneration, DocumentIndexGeneration.id == DocumentChunk.generation_id)
        .join(Document, (Document.id == DocumentChunk.document_id) & (Document.student_id == DocumentChunk.student_id))
        .where(
            DocumentChunk.student_id == student_id,
            DocumentIndexState.student_id == student_id,
            DocumentIndexState.active_generation_id == DocumentChunk.generation_id,
            DocumentIndexGeneration.status == "ready",
            Document.processing_status == "processed",
            DocumentChunk.embedding_model == model,
            DocumentChunk.embedding_dimensions == 768,
        )
    )
    if db.bind.dialect.name == "postgresql":
        distance = DocumentChunk.embedding.cosine_distance(query_vector)
        rows = db.execute(statement.add_columns(distance.label("distance")).order_by(distance.asc(), DocumentChunk.id.asc()).limit(top_k)).all()
        return [
            {"document_id": chunk.document_id, "document_name": name, "page_number": chunk.page_number,
             "ordinal": chunk.ordinal, "content": chunk.content, "score": max(-1.0, min(1.0, 1.0 - float(dist))), "chunk_id": chunk.id}
            for chunk, name, dist in rows
        ]
    rows = db.execute(statement.order_by(DocumentChunk.id.asc())).all()
    scored = []
    query_norm = math.sqrt(sum(value * value for value in query_vector))
    for chunk, name in rows:
        denominator = query_norm * math.sqrt(sum(value * value for value in chunk.embedding))
        score = sum(a * b for a, b in zip(query_vector, chunk.embedding, strict=True)) / denominator if denominator else 0.0
        scored.append((score, chunk.id, chunk, name))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [
        {"document_id": chunk.document_id, "document_name": name, "page_number": chunk.page_number,
         "ordinal": chunk.ordinal, "content": chunk.content, "score": score, "chunk_id": chunk.id}
        for score, _, chunk, name in scored[:top_k]
    ]
