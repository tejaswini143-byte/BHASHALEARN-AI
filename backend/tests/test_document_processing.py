"""Private PDF document API, validation, persistence, and ownership tests."""
from hashlib import sha256

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import Document, DocumentPage
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.documents import PrivateDocumentStorage, normalize_extracted_text


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    monkeypatch.setenv("BHASHALEARN_DOCUMENT_STORAGE_DIR", str(tmp_path / "private-docs"))
    monkeypatch.setenv("BHASHALEARN_DOCUMENT_MAX_UPLOAD_BYTES", "4096")
    monkeypatch.setenv("BHASHALEARN_DOCUMENT_MAX_PAGES", "3")
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


@pytest.fixture
def client(env):
    engine = create_engine(f"sqlite:///{(env / 'documents.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def auth(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def pdf_bytes(*texts):
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def upload(client, headers, content=None, filename="lesson.pdf", content_type="application/pdf"):
    return client.post("/api/v1/documents", headers=headers, files={"file": (filename, content if content is not None else pdf_bytes("Fractions are equal parts."), content_type)})


def test_document_routes_require_authentication(client):
    assert client.post("/api/v1/documents", files={"file": ("a.pdf", pdf_bytes("x"), "application/pdf")}).status_code == 401
    assert client.get("/api/v1/documents").status_code == 401
    assert client.get("/api/v1/documents/unknown").status_code == 401
    assert client.get("/api/v1/documents/unknown/pages").status_code == 401
    assert client.delete("/api/v1/documents/unknown").status_code == 401


def test_upload_extracts_and_persists_page_text(client, env):
    headers = auth(client, "doc-one@example.com")
    response = upload(client, headers, pdf_bytes("Fractions are equal parts.", "A half is one of two equal parts."), "fractions.pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["original_filename"] == "fractions.pdf"
    assert body["mime_type"] == "application/pdf"
    assert body["file_size_bytes"] > 0
    assert body["page_count"] == 2
    assert body["processing_status"] == "processed"
    assert "storage_key" not in body and "storage_path" not in body
    pages = client.get(f"/api/v1/documents/{body['id']}/pages", headers=headers)
    assert pages.status_code == 200
    assert pages.json()["total"] == 2
    assert pages.json()["items"][0]["page_number"] == 1
    assert "Fractions are equal parts." in pages.json()["items"][0]["extracted_text"]
    listed = client.get("/api/v1/documents", headers=headers).json()
    assert [item["id"] for item in listed] == [body["id"]]
    assert (env / "private-docs" / f"{body['id']}.pdf").exists()


def test_textless_pdf_is_reported_without_claiming_ocr(client):
    headers = auth(client, "empty-text@example.com")
    response = upload(client, headers, pdf_bytes(""))
    assert response.status_code == 201
    body = response.json()
    assert body["processing_status"] == "text_extraction_unavailable"
    pages = client.get(f"/api/v1/documents/{body['id']}/pages", headers=headers).json()
    assert pages["items"][0]["extracted_text"] == ""


def test_password_protected_pdf_is_rejected(client):
    protected = fitz.open()
    protected.new_page().insert_text((72, 72), "Private")
    content = protected.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="student")
    protected.close()
    headers = auth(client, "encrypted@example.com")
    response = upload(client, headers, content)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "encrypted_pdf"


def test_missing_file_field_is_rejected(client):
    headers = auth(client, "missing-file@example.com")
    response = client.post("/api/v1/documents", headers=headers, data={})
    assert response.status_code == 422


def test_corrupt_pdf_body_is_rejected_and_temp_file_removed(client, env):
    headers = auth(client, "corrupt@example.com")
    response = upload(client, headers, b"%PDF-1.7\nthis is not a valid xref or page tree")
    assert response.status_code == 422
    # On Windows this catches leaked handles that prevent deletion (WinError 32).
    assert list((env / "private-docs").iterdir()) == []


@pytest.mark.parametrize(("filename", "content", "status", "code"), [
    ("note.txt", pdf_bytes("valid text"), 422, "unsupported_file_type"),
    ("bad.pdf", b"not actually a pdf", 422, "invalid_pdf_signature"),
    ("bad.pdf", b"", 422, "empty_upload"),
    ("../escape.pdf", pdf_bytes("valid"), 422, "invalid_filename"),
    ("x" * 253 + ".pdf", pdf_bytes("valid"), 422, "invalid_filename"),
])
def test_invalid_uploads_are_rejected(client, filename, content, status, code):
    email_suffix = sha256(filename.encode()).hexdigest()[:8]
    headers = auth(client, f"invalid-{code}-{email_suffix}@example.com")
    response = upload(client, headers, content, filename)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_size_and_page_limits_are_enforced(client):
    headers = auth(client, "limits@example.com")
    too_large = upload(client, headers, b"%PDF-" + b"x" * 5000)
    assert too_large.status_code == 413
    assert too_large.json()["detail"]["code"] == "file_too_large"
    too_many_pages = upload(client, headers, pdf_bytes("1", "2", "3", "4"))
    assert too_many_pages.status_code == 413
    assert too_many_pages.json()["detail"]["code"] == "too_many_pages"


def test_spoofed_content_type_does_not_override_pdf_validation(client):
    headers = auth(client, "spoof@example.com")
    response = upload(client, headers, b"<html>not pdf</html>", "spoof.pdf", "application/pdf")
    assert response.status_code == 422


def test_document_ownership_and_no_existence_disclosure(client):
    owner = auth(client, "owner@example.com")
    other = auth(client, "other@example.com")
    created = upload(client, owner).json()
    assert client.get("/api/v1/documents", headers=other).json() == []
    assert client.get(f"/api/v1/documents/{created['id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/documents/{created['id']}/pages", headers=other).status_code == 404
    assert client.delete(f"/api/v1/documents/{created['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/documents/not-real", headers=other).status_code == 404


def test_delete_removes_metadata_pages_and_private_file(client, env):
    headers = auth(client, "delete@example.com")
    created = upload(client, headers, pdf_bytes("Page one", "Page two")).json()
    path = env / "private-docs" / f"{created['id']}.pdf"
    assert path.exists()
    response = client.delete(f"/api/v1/documents/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/v1/documents/{created['id']}", headers=headers).status_code == 404
    assert not path.exists()
    # The second delete is safely idempotent at the resource boundary.
    assert client.delete(f"/api/v1/documents/{created['id']}", headers=headers).status_code == 404


def test_document_listing_paginates_newest_first(client):
    headers = auth(client, "pages@example.com")
    first = upload(client, headers, filename="one.pdf").json()
    second = upload(client, headers, filename="two.pdf").json()
    assert client.get("/api/v1/documents?limit=0", headers=headers).status_code == 422
    listed = client.get("/api/v1/documents?limit=1&offset=0", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["id"] == second["id"]
    assert first["id"] != second["id"]


def test_page_response_pagination(client):
    headers = auth(client, "page-list@example.com")
    document = upload(client, headers, pdf_bytes("one", "two")).json()
    response = client.get(f"/api/v1/documents/{document['id']}/pages?limit=1&offset=1", headers=headers)
    assert response.status_code == 200
    assert response.json()["items"][0]["page_number"] == 2


def test_extracted_text_normalization_preserves_telugu_unicode():
    text = normalize_extracted_text("  మిశ్రమ  భిన్నం  \x00\n\n అంటే ఏమిటి?  ")
    assert text == "మిశ్రమ భిన్నం\nఅంటే ఏమిటి?"


def test_storage_key_collision_does_not_overwrite_existing_pdf(tmp_path):
    storage = PrivateDocumentStorage(tmp_path / "private")
    document_id = "12345678-1234-1234-1234-123456789abc"
    target = storage.root / storage.key_for(document_id)
    target.write_bytes(b"existing")
    temporary = storage.new_temp_path()
    temporary.write_bytes(b"new upload")
    with pytest.raises(FileExistsError):
        storage.finalize(temporary, storage.key_for(document_id))
    assert target.read_bytes() == b"existing"
    assert temporary.exists()


def test_storage_finalize_failure_leaves_no_document_or_temp_file(client, env, monkeypatch):
    from backend.app.api import documents as documents_api

    headers = auth(client, "storage-failure@example.com")
    def fail_finalize(self, temp_path, storage_key):
        raise OSError("simulated storage failure")
    monkeypatch.setattr(documents_api.PrivateDocumentStorage, "finalize", fail_finalize)
    response = upload(client, headers)
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "document_processing_failed"
    assert client.get("/api/v1/documents", headers=headers).json() == []
    assert list((env / "private-docs").iterdir()) == []


def test_database_failure_rolls_back_and_removes_final_file(client, env, monkeypatch):
    headers = auth(client, "database-failure@example.com")
    original_commit = Session.commit
    def fail_document_commit(self):
        if any(isinstance(value, DocumentPage) for value in self.new):
            raise RuntimeError("simulated database failure")
        return original_commit(self)
    monkeypatch.setattr(Session, "commit", fail_document_commit)
    response = upload(client, headers)
    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "document_processing_failed"
    assert client.get("/api/v1/documents", headers=headers).json() == []
    assert list((env / "private-docs").iterdir()) == []
