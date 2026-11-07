# ADV-02 — Embeddings and Vector Storage

## Scope

ADV-02 extends authenticated ADV-01 private PDF processing with deterministic
page-level chunks, Gemini text embeddings, PostgreSQL pgvector storage, safe
index retries, and student-scoped semantic retrieval. It does not generate
answers, add chat grounding, or change the tutoring conversation flow.

## Chunking

`backend/app/services/chunking.py` normalizes each extracted page to Unicode
NFC, removes NUL bytes, and collapses whitespace. Each page is split
independently so a chunk never crosses a PDF page boundary. The target is
1,000 Unicode code points with 150 code points of overlap. Splits prefer
whitespace in the last quarter of the target; an individual grapheme may
exceed the target rather than be split. Combining marks, variation selectors,
emoji modifiers, ZWJ sequences, flag pairs, and Indic virama conjuncts remain
together. These settings can be changed in the backend environment; any
chunking change changes the source fingerprint and triggers a new generation.

Each ordered chunk records its page, document, ordinal, normalized text,
SHA-256 content hash, deterministic SHA-256 identifier, and chunking version.
Empty pages and whitespace-only text produce no chunk. Repeated text at
different positions remains distinct because the stable ID includes document,
page, ordinal, and content hash.

## Provider and privacy

The adapter uses the supported Gemini API REST `batchEmbedContents` method and
`gemini-embedding-001`, with `RETRIEVAL_DOCUMENT` for indexed chunks and
`RETRIEVAL_QUERY` for search queries. The configured output size is 768 values;
Google documents this as a supported reduced dimension. Reduced output vectors
are normalized before storage and search. The pgvector column and database
constraints are fixed at 768 dimensions. A different configured dimension is
rejected until a deliberate schema migration is made.

The provider uses batches of at most 16 texts, a 20-second timeout, and up to
two bounded retries for timeouts, network failures, HTTP 429, and transient
5xx responses. Invalid responses, wrong dimensions, non-finite numbers, and
zero vectors fail the indexing attempt. Errors never include request text or
the API key. The embedding-specific key variable is preferred; the existing
Gemini server key is used as a fallback. Keep credentials in the ignored root
`.env` or server environment, never in frontend variables.

**Privacy behavior changes only when the student chooses indexing or search.**
On explicit indexing, extracted PDF text is sent to the configured Gemini
embedding service. On search, the query is sent to that service. The uploaded
PDF remains in ADV-01 private storage; no file or student-owned data is sent
automatically at upload time. Google service terms and retention apply to those
explicit provider requests.

## Schema and lifecycle

Migration `0008_document_embeddings` follows `0007_private_documents`. It
adds `document_index_generations`, `document_index_states`, and
`document_chunks`, plus a unique owner-pair index on `documents`. Composite
foreign keys bind every state, generation, and chunk to the owning document
and student. Document deletion cascades through all index records. The
migration requires the already-enabled `vector` extension and does not install
it.

An indexing request locks the student-owned document row. A competing request
receives HTTP 409 while the current attempt is active. Embeddings are generated
outside the chunk insert transaction in bounded provider batches. A new
generation remains hidden until all chunk vectors are validated and inserted;
one transaction marks it ready and switches the active generation. The old
generation is removed in that transaction. Provider failure marks the new
generation failed while leaving the previous ready generation searchable.
Unchanged source/model/dimension/chunk settings return the existing ready
generation without another provider call. Interrupted processing can be
retried after its ten-minute heartbeat timeout.

The initial dataset uses exact cosine-distance scans with stable chunk-ID tie
breaking. No approximate HNSW/IVFFlat index is created because there is no
measured corpus size or query workload to justify approximate results yet. The
owner/document and generation/status B-tree indexes support filters and stable
metadata lookups.

## API

All endpoints require the existing bearer token and use the authenticated
student ID in document lookup or vector retrieval SQL.

| Method and route | Behavior |
| --- | --- |
| `POST /api/v1/documents/{document_id}/index` | Index or retry a private document; `?force=true` explicitly rebuilds it. |
| `GET /api/v1/documents/{document_id}/index-status` | Return the current attempt and active generation metadata. |
| `POST /api/v1/documents/search` | Search current ready generations. JSON: `{"query":"fractions in Telugu","top_k":5}`. |

Search returns `model`, `dimensions`, and `items`. Each item includes its
document ID/name, page number, ordinal, text, chunk ID, and cosine similarity
score from -1 to 1 (higher is more similar). `top_k` is limited to 1–20 and
query text to 1,000 characters. A student cannot index, inspect status for, or
retrieve another student's document, even with a guessed document ID.

## Frontend

The existing `/documents/{id}` detail page shows pending, processing, ready,
or failed state and offers **Index document**, **Retry indexing**, or
**Reindex document** actions. The Documents page provides an authenticated
semantic search box and displays matching page excerpts and similarity scores.
It shows loading, empty, and error states. Upload itself does not submit
extracted text to Gemini.

## Local setup and verification

The isolated database URL can omit its password when PostgreSQL's local
`pgpass.conf` supplies the dedicated role credential:

```cmd
set BHASHALEARN_DATABASE_URL=postgresql+psycopg://bhashalearn_adv02@127.0.0.1:5432/bhashalearn_adv02_test
```

Check identity and extension before migrations. Only the dedicated database
`bhashalearn_adv02_test` is allowed for ADV-02 database writes. Never point
these commands at `bhashalearn` or `bhashalearn_e2e_test`.

```cmd
.venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.venv\Scripts\python.exe -m pytest -q backend\tests
```

The PostgreSQL integration tests refuse any other database/role and require
the migration head plus pgvector 0.8.7:

```cmd
set BHASHALEARN_ADV02_TEST_DATABASE_URL=postgresql+psycopg://bhashalearn_adv02@127.0.0.1:5432/bhashalearn_adv02_test
.venv\Scripts\python.exe -m pytest -q backend\tests\test_document_indexing_postgres.py
```

The URL deliberately contains no password; libpq reads it from the local
password file. Unit tests use SQLite and mocked provider responses. A live
Gemini smoke test requires an already configured server key and is separate
from the mocked provider suite.

## Troubleshooting

- HTTP 503 from indexing/search: set the server-side embedding key and confirm
  model `gemini-embedding-001` and dimension `768`.
- HTTP 502: the embedding provider timed out, rejected the request, exhausted
  quota, or returned a malformed response; retry after resolving the provider
  condition. The API deliberately hides provider response bodies.
- HTTP 409: another indexing request is active. Wait for it to finish; an
  abandoned attempt becomes retryable after its heartbeat has been stale for
  ten minutes.
- Migration says vector extension is missing: enable pgvector in the isolated
  ADV-02 database before running the migration; do not install it elsewhere.
