"""Bounded PDF validation, page-text extraction, and private file storage."""
from __future__ import annotations

import re
import time
from pathlib import Path
from uuid import uuid4

import fitz


class DocumentInputError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class DocumentCleanupError(OSError):
    """A private upload artifact could not be removed after bounded retries."""


def _unlink_with_retry(path: Path, *, attempts: int = 5) -> None:
    for attempt in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt + 1 == attempts:
                raise DocumentCleanupError("Private document cleanup failed after retries.") from None
            # Windows may briefly retain a handle while the parser/runtime releases it.
            time.sleep(0.05 * (attempt + 1))
        except OSError:
            raise DocumentCleanupError("Private document cleanup failed.") from None


def normalize_extracted_text(value: str) -> str:
    """Remove parser NULs and normalize whitespace without transliterating Unicode."""
    value = value.replace("\x00", "")
    value = "\n".join(line.strip() for line in value.splitlines() if line.strip())
    return re.sub(r"[ \t]+", " ", value)


def validate_filename(filename: str | None, maximum: int) -> str:
    value = filename or ""
    if not value or len(value) > maximum:
        raise DocumentInputError("invalid_filename", f"Filename must contain 1 to {maximum} characters.")
    if Path(value).name != value or "/" in value or "\\" in value or value in {".", ".."}:
        raise DocumentInputError("invalid_filename", "Filename must not contain a path.")
    if not value.lower().endswith(".pdf"):
        raise DocumentInputError("unsupported_file_type", "Choose a PDF file.")
    return value


def extract_pdf_pages(path: Path, *, max_pages: int, max_characters: int) -> tuple[list[str], str]:
    """Open and parse a PDF, returning normalized text per page and a safe status."""
    try:
        # Parse bounded bytes instead of the path. PyMuPDF then owns no Windows
        # file handle for the temporary upload, including on parse failures.
        content = path.read_bytes()
        if content[:5] != b"%PDF-":
            raise DocumentInputError("invalid_pdf_signature", "The file is not a valid PDF.")
        pdf = fitz.open(stream=content, filetype="pdf")
    except DocumentInputError:
        raise
    except Exception as exc:
        raise DocumentInputError("corrupted_pdf", "The PDF is corrupted or cannot be opened.") from exc
    try:
        if pdf.needs_pass:
            raise DocumentInputError("encrypted_pdf", "Password-protected PDFs are not supported.")
        if pdf.page_count < 1:
            raise DocumentInputError("empty_pdf", "The PDF does not contain any pages.")
        if pdf.page_count > max_pages:
            raise DocumentInputError("too_many_pages", f"PDFs may contain at most {max_pages} pages.", 413)
        pages: list[str] = []
        total = 0
        for page in pdf:
            text = normalize_extracted_text(page.get_text("text"))
            total += len(text)
            if total > max_characters:
                raise DocumentInputError("extracted_text_too_large", "The extracted PDF text exceeds the processing limit.", 413)
            pages.append(text)
        status = "processed" if any(page.strip() for page in pages) else "text_extraction_unavailable"
        return pages, status
    finally:
        pdf.close()


class PrivateDocumentStorage:
    """Opaque UUID-keyed storage rooted outside public frontend assets."""
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def new_temp_path(self) -> Path:
        return self.root / f".{uuid4().hex}.upload"

    def remove_temp(self, temp_path: Path) -> None:
        resolved = temp_path.resolve()
        if resolved.parent != self.root or not re.fullmatch(r"\.[0-9a-f]{32}\.upload", resolved.name):
            raise ValueError("Invalid temporary upload path")
        _unlink_with_retry(resolved)

    def key_for(self, document_id: str) -> str:
        return f"{document_id}.pdf"

    def finalize(self, temp_path: Path, storage_key: str) -> Path:
        target = (self.root / storage_key).resolve()
        if target.parent != self.root or not re.fullmatch(r"[0-9a-fA-F-]{36}\.pdf", storage_key):
            raise ValueError("Invalid private storage key")
        temp_resolved = temp_path.resolve()
        if temp_resolved.parent != self.root:
            raise ValueError("Temporary upload is outside private storage")
        # Exclusive creation prevents a UUID collision from replacing another upload.
        created_target = False
        try:
            with temp_path.open("rb") as source, target.open("xb") as destination:
                created_target = True
                while chunk := source.read(64 * 1024):
                    destination.write(chunk)
        except Exception:
            if created_target:
                target.unlink(missing_ok=True)
            raise
        try:
            self.remove_temp(temp_path)
        except Exception:
            # Do not leave a finalized PDF behind if its upload temporary cannot
            # be removed. The caller receives the cleanup failure explicitly.
            _unlink_with_retry(target)
            raise
        return target

    def delete(self, storage_key: str) -> None:
        if not re.fullmatch(r"[0-9a-fA-F-]{36}\.pdf", storage_key):
            raise ValueError("Invalid private storage key")
        target = (self.root / storage_key).resolve()
        if target.parent != self.root:
            raise ValueError("Storage key escaped private storage")
        _unlink_with_retry(target)
