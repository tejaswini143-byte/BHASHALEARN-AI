# ADV-01 — PDF Upload and Document Processing

## Objective and scope

ADV-01 adds authenticated, student-owned PDF upload, private local storage,
page-level text extraction, listing, details, and deletion. It is document
management only: no embeddings, vector store, retrieval, OCR, or
document-grounded Gemini response is implemented. Uploaded contents are not
sent to Gemini or Gnani.

## Architecture

The React Documents page uses the existing bearer-token API helper. The helper
leaves the `Content-Type` header unset for `FormData`, allowing the browser to
set the multipart boundary. FastAPI routes use the existing `current_student`
dependency and scope every document query by authenticated `student_id`.
`PrivateDocumentStorage` generates opaque UUID filenames under a configurable
private directory. PyMuPDF validates/parses files and extracts text by page.
Document metadata and page text are persisted in PostgreSQL through SQLAlchemy.

The frontend route is `/documents`; details are at `/documents/{document_id}`.
The Dashboard's Learning Studios navigation links to Documents. Lists, detail
metadata, and page text are fetched from the backend after navigation/refresh.
Delete requires browser confirmation.

## API contract

All routes are under `/api/v1/documents` and require `Authorization: Bearer …`.

| Method and route | Result |
| --- | --- |
| `POST /api/v1/documents` | Multipart field `file`; returns metadata and processing status (201). |
| `GET /api/v1/documents?limit=20&offset=0` | Current student's newest documents. |
| `GET /api/v1/documents/{id}` | Current student's metadata; missing and foreign IDs both return 404. |
| `GET /api/v1/documents/{id}/pages?limit=20&offset=0` | Bounded, page-number-ordered text records. |
| `DELETE /api/v1/documents/{id}` | Removes database metadata/page rows and private file (204). |

Responses never expose `storage_key` or filesystem paths. Validation errors use
safe `detail.code` and `detail.message`. Unknown and cross-student IDs share a
not-found response.

## Persistence and migration

Migration `0007_private_documents` follows `0006_adaptive_learning_memory`.
It adds `documents` and `document_pages`, ownership and page indexes, cascade
foreign keys, a unique `(document_id, page_number)` constraint, and basic
nonnegative/status checks. Downgrade drops only these new tables. The migration
must be tested on a disposable database. It has **not** been applied to any
existing persistent database as part of this work.

Before applying it to a local development database, make and verify a database
backup, confirm the configured database target, then run the migration command
below. Never apply it to production as part of this POC.

## Upload limits and extraction

The defaults are 10 MiB (`BHASHALEARN_DOCUMENT_MAX_UPLOAD_BYTES`), 100 pages,
2,000,000 extracted characters per PDF, and a 255-character filename. Settings
are configurable in `backend/.env.example`. Upload bytes are read in bounded
64 KiB chunks, the filename is metadata only, and storage uses a server-side
UUID key. Both the `.pdf` extension and `%PDF-` signature are checked, then
PyMuPDF must parse the file. Password-protected, corrupt, empty, over-limit,
and too-many-page inputs are rejected. The upload MIME header is not trusted.
PyMuPDF receives the bounded bytes as an in-memory stream rather than opening
the temporary path, so parse failures do not retain a Windows file handle.
Private temporary-file removal retries transient Windows sharing violations a
bounded number of times; a final cleanup failure is surfaced as a safe
`document_cleanup_failed` error instead of being ignored.

Text is stored per page with page number and character count. Unicode is
preserved; only NUL bytes and excess whitespace are normalized. A valid file
with no extractable text is retained with status
`text_extraction_unavailable` and an empty page record; this can indicate a
scanned/image-only PDF. OCR is not available. The processing path is
synchronous, bounded by byte, page, and extracted-character limits.

If database persistence fails after the file is finalized, the request rolls
back and removes the file. Deletion commits metadata removal and then removes
the private file. If unlinking fails, the API returns a safe cleanup error; the
orphaned file remains private and requires administrator cleanup.

## Security

- Every operation requires authentication and uses the authenticated student;
  client-supplied owner IDs are not accepted.
- Private files are stored outside frontend static assets and the directory is
  gitignored. Public file download is not exposed.
- Path components are rejected in client filenames; client names never become
  storage paths.
- Upload size is enforced while reading; page/text limits bound parser output.
- Document contents and extracted text are not logged or sent to providers.
- Error responses do not expose tracebacks or private paths.
- No actual `.env` or credential was modified.

## Windows CMD setup and run

From the repository root, after a local backup and confirmation that the
configured database is the intended development database:

```cmd
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m alembic -c backend\alembic.ini upgrade head
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8002
```

In a second CMD window:

```cmd
cd frontend
set BHASHALEARN_API_PROXY_TARGET=http://127.0.0.1:8002
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Open the Vite URL, log in, then choose **Documents** in the Dashboard's
Learning Studios navigation. `npm.cmd run build` verifies the production app.

## Tests

Backend tests use a temporary SQLite database, temporary private storage, and
generated PDFs; they do not require live credentials. Run:

```cmd
python -m pytest -q backend\tests\test_document_processing.py
python -m pytest -q backend\tests
set PYTHONPATH=%CD%\pocs\poc01_prisma_stt;%CD%\pocs\poc02_timbre_tts;%CD%\pocs\poc06_bilingual_voice;%CD%
python -m pytest -q pocs\poc01_prisma_stt\tests pocs\poc02_timbre_tts\tests pocs\poc06_bilingual_voice\tests
cd frontend
npm.cmd test
npm.cmd run build
```

The migration's upgrade/downgrade is exercised by the existing migration test
against its temporary SQLite database. Do not point that test or migrations at
the persistent development PostgreSQL database.

## Browser acceptance checklist

1. Log in and open Documents.
2. Upload a generated text-based PDF; verify success, list metadata, and page
   text.
3. Refresh and verify the document remains listed and its details still load.
4. Upload an invalid/spoofed PDF and verify a clear validation error.
5. Upload an image-only PDF and verify the no-selectable-text message.
6. Delete a document and verify it disappears from the list.
7. Log in as another test student and verify the first student's document is
   neither listed nor accessible by ID.

## Known limitations and ADV-02 integration points

- Local filesystem storage is suitable for development, not horizontally
  scaled production deployment; a future storage adapter can replace it.
- No OCR for scanned pages.
- No document download endpoint.
- No embeddings, semantic search, RAG, or document-grounded tutoring; those
  belong to later ADV work.
- Browser upload shows a clear processing/loading state, not byte-level upload
  percentage (the current fetch API does not expose upload progress).
- Python and the backend server were unavailable in the current Codex
  worktree environment; see the execution report for actual checks and exact
  local commands still required.

## Execution results (2026-11-05)

- Frontend dependency install: `npm.cmd ci` completed (73 packages; 0 reported
  vulnerabilities).
- Frontend tests: `npm.cmd test` — 9 passed, 0 failed.
- Frontend production build: `npm.cmd run build` — TypeScript passed and Vite
  transformed 61 modules successfully.
- Backend targeted/full tests and migration tests: **not executed**. This
  environment has no `python` command, no `py` launcher, no project `.venv`,
  and `uv` cannot read its managed Python installation directory.
- Gnani POC regressions: **not executed** for the same Python limitation.
- Backend/API and real-browser acceptance: **blocked** because the backend
  could not start. Vite dev startup also failed in this sandbox when its
  transform subprocess attempted to read outside the allowed worktree; the
  production build succeeded using Vite's runner config loader.
- Migration `0007_private_documents` was not applied to any database.
- Root `git diff --check`: passed; no commit or push was made.

## ADV-01 worktree database configuration

The application settings use `SettingsConfigDict(env_file=".env")` and
`BHASHALEARN_` as the environment prefix. The `.env` lookup is relative to the
process working directory; a separate Git worktree does not inherit the
original repository's ignored root `.env`. If no environment variable or
worktree-local `.env` supplies `BHASHALEARN_DATABASE_URL`, settings fall back
to the development default declared in `backend/app/config.py`. That default
may have different credentials from the local PostgreSQL credentials used by
the original worktree. No secret file was copied or inspected to diagnose this.

To configure ADV-01, edit the ignored root file
`C:\Users\Tejaswini\BHASHALEARN-ADV01\.env` locally and set
`BHASHALEARN_DATABASE_URL` to the same local development database URL that
works for the student's `psql` connection. URL-encode reserved characters in
the password. Do not paste credentials into chat or commit this file. Do not
run `alembic upgrade` until the target database is confirmed and backed up.
