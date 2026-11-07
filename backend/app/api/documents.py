"""Authenticated private PDF document management endpoints."""
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.config import get_settings
from backend.app.db.models import Document, DocumentPage, Student
from backend.app.db.session import get_db
from backend.app.services.document_index import IndexingError, index_document, index_status, search_documents
from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider
from backend.app.services.documents import DocumentCleanupError, DocumentInputError, PrivateDocumentStorage, extract_pdf_pages, validate_filename

router = APIRouter(prefix="/documents", tags=["documents"])


def get_embedding_provider() -> GeminiEmbeddingProvider:
    return GeminiEmbeddingProvider()


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    page_count: int | None
    processing_status: str
    processing_error_code: str | None
    created_at: datetime
    updated_at: datetime


class DocumentPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    page_number: int
    extracted_text: str
    character_count: int


class DocumentPageList(BaseModel):
    document_id: str
    total: int
    items: list[DocumentPageResponse]


class DocumentIndexResponse(BaseModel):
    document_id: str
    status: str
    error_code: str | None = None
    chunk_count: int = 0
    embedding_model: str | None = None
    embedding_dimensions: int | None = None
    updated_at: datetime


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def query_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must contain non-whitespace text")
        return value.strip()


class SemanticSearchItem(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_number: int
    ordinal: int
    content: str
    score: float = Field(ge=-1, le=1)


class SemanticSearchResponse(BaseModel):
    model: str
    dimensions: int
    items: list[SemanticSearchItem]


def _owned(document_id: str, student: Student, db: Session) -> Document:
    item = db.scalar(select(Document).where(Document.id == document_id, Document.student_id == student.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return item


def _cleanup_upload(
    storage: PrivateDocumentStorage | None,
    temp_path: Path | None,
    storage_key: str | None,
    finalized: bool,
) -> None:
    """Attempt every applicable cleanup and surface failure without exposing paths."""
    if storage is None:
        return
    failed = False
    if temp_path is not None:
        try:
            storage.remove_temp(temp_path)
        except OSError:
            failed = True
    if finalized and storage_key is not None:
        try:
            storage.delete(storage_key)
        except OSError:
            failed = True
    if failed:
        raise DocumentCleanupError("Private document cleanup failed.")


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    try:
        filename = validate_filename(file.filename, settings.document_max_filename_length)
    except DocumentInputError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    storage: PrivateDocumentStorage | None = None
    temp_path: Path | None = None
    storage_key: str | None = None
    finalized = False
    size = 0
    try:
        storage = PrivateDocumentStorage(settings.document_storage_dir)
        temp_path = storage.new_temp_path()
        with temp_path.open("xb") as target:
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > settings.document_max_upload_bytes:
                    limit = settings.document_max_upload_bytes
                    label = f"{limit / (1024 * 1024):g} MB" if limit >= 1024 * 1024 else f"{max(1, limit // 1024)} KB"
                    raise DocumentInputError("file_too_large", f"PDFs may be at most {label}.", 413)
                target.write(chunk)
        if size == 0:
            raise DocumentInputError("empty_upload", "The selected file is empty.")
        pages, processing_status = extract_pdf_pages(
            temp_path,
            max_pages=settings.document_max_pages,
            max_characters=settings.document_max_extracted_characters,
        )
        document_id = str(uuid4())
        storage_key = storage.key_for(document_id)
        storage.finalize(temp_path, storage_key)
        finalized = True
        document = Document(
            id=document_id,
            student_id=student.id,
            original_filename=filename,
            storage_key=storage_key,
            mime_type="application/pdf",
            file_size_bytes=size,
            page_count=len(pages),
            processing_status=processing_status,
            processing_error_code="TEXT_EXTRACTION_UNAVAILABLE" if processing_status == "text_extraction_unavailable" else None,
        )
        db.add(document)
        db.flush()
        db.add_all(DocumentPage(document_id=document_id, page_number=index, extracted_text=text, character_count=len(text)) for index, text in enumerate(pages, start=1))
        db.commit()
        db.refresh(document)
        return document
    except DocumentInputError as exc:
        db.rollback()
        try:
            _cleanup_upload(storage, temp_path, storage_key, finalized)
        except DocumentCleanupError:
            raise HTTPException(status_code=500, detail={"code": "document_cleanup_failed", "message": "The upload was rejected, but temporary file cleanup failed. Contact support before retrying."}) from None
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    except Exception as exc:
        db.rollback()
        try:
            _cleanup_upload(storage, temp_path, storage_key, finalized)
        except DocumentCleanupError:
            raise HTTPException(status_code=500, detail={"code": "document_cleanup_failed", "message": "Document processing failed and private file cleanup needs attention."}) from None
        raise HTTPException(status_code=500, detail={"code": "document_processing_failed", "message": "The document could not be processed. Please retry."}) from exc
    finally:
        await file.close()


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    student: Student = Depends(current_student), db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
):
    return db.scalars(select(Document).where(Document.student_id == student.id).order_by(Document.created_at.desc(), Document.id.desc()).offset(offset).limit(limit)).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return _owned(document_id, student, db)


@router.get("/{document_id}/pages", response_model=DocumentPageList)
def get_document_pages(
    document_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
):
    document = _owned(document_id, student, db)
    total = db.query(DocumentPage).filter(DocumentPage.document_id == document.id).count()
    items = db.scalars(select(DocumentPage).where(DocumentPage.document_id == document.id).order_by(DocumentPage.page_number.asc()).offset(offset).limit(limit)).all()
    return DocumentPageList(document_id=document.id, total=total, items=items)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    document = _owned(document_id, student, db)
    storage_key = document.storage_key
    try:
        storage = PrivateDocumentStorage(get_settings().document_storage_dir)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Private document storage is unavailable. Try again later.") from exc
    db.delete(document)
    db.commit()
    try:
        storage.delete(storage_key)
    except OSError:
        raise HTTPException(status_code=500, detail={"code": "document_file_cleanup_failed", "message": "Document metadata was removed, but private file cleanup failed. Contact support."}) from None


@router.get("/{document_id}/index-status", response_model=DocumentIndexResponse)
def get_document_index_status(
    document_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    try:
        return index_status(db, document_id=document_id, student_id=student.id)
    except IndexingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None


@router.post("/{document_id}/index", response_model=DocumentIndexResponse)
def index_private_document(
    document_id: str,
    force: bool = Query(False),
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    provider: GeminiEmbeddingProvider = Depends(get_embedding_provider),
):
    try:
        settings = get_settings()
        return index_document(
            db, document_id=document_id, student_id=student.id, provider=provider, force=force,
            chunk_size=settings.embedding_chunk_size, overlap=settings.embedding_chunk_overlap,
        )
    except IndexingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None


@router.post("/search", response_model=SemanticSearchResponse)
def semantic_search(
    payload: SemanticSearchRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    provider: GeminiEmbeddingProvider = Depends(get_embedding_provider),
):
    if provider.dimensions != 768:
        raise HTTPException(status_code=503, detail={"code": "embedding_configuration_mismatch", "message": "Embedding configuration does not match vector storage."})
    try:
        query_vector = provider.embed_texts([payload.query], task_type="RETRIEVAL_QUERY")[0]
    except EmbeddingError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": "embedding_provider_unavailable", "message": str(exc)}) from None
    items = search_documents(db, student_id=student.id, query_vector=query_vector, model=provider.model, top_k=payload.top_k)
    return SemanticSearchResponse(model=provider.model, dimensions=provider.dimensions, items=items)
