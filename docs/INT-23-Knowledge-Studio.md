# INT-23 Knowledge Studio

## Reused architecture

INT-23 extends the authenticated document and retrieval stack in the source classroom: ADV01's bounded PDF parser/private storage, ADV02's page-aware chunking and versioned pgvector index, and ADV03's untrusted-evidence RAG prompt and citation attribution. Embeddings use the already configured `GeminiEmbeddingProvider`; answer generation uses the existing configured tutor adapter. No provider URL, key, or database technology is introduced here.

The library remains in `documents` and `document_pages`; active chunks remain in `document_chunks` and are filtered by owner, document, active generation and embedding model. `/api/v1/knowledge/ask` and `/api/v1/knowledge/learning` require the existing bearer-authenticated student. Each request names up to ten document IDs. The API verifies ownership, extraction state and ready indexes before retrieval, and the vector query also applies that student ID plus the selected ID filter. Knowledge generation endpoints enforce a per-student process-local limit of 30 requests per minute.

## API contract

- `POST /api/v1/knowledge/ask`: `{ document_ids, question, language, history? }` returns `answer`, validated `citations` (`document_id`, title, page), `grounded`, `retrieval_used`, and an `uncertainty` message when no sufficiently relevant passage is retrieved.
- `POST /api/v1/knowledge/learning`: `{ document_ids, mode, topic?, language }`, where mode is `summary`, `concepts`, `flashcards`, `practice`, or `quiz`. Text materials are returned as `content`; quiz material is schema-checked and includes answer choices, a validated correct index, explanation and supplied citation IDs. The browser checks submitted choices against the generated answer key.
- Citation navigation opens `/documents/{document_id}?page={page}`. That detail page paginates to the referenced page.

The `VectorPassageRetriever` accepts an optional set of document IDs while retaining the authenticated student scope. Classroom integrations can call the same backend retrieval contract with a validated student identity and pass the returned `RetrievedPassage` values to their own quiz, teaching, holographic teacher, voice, or roadmap adapters. Do not pass browser-supplied owner IDs as authorization; integrations must derive the student from the authenticated request. Never log passage bodies.

INT13 adaptive quizzes can consume the validated document quiz response or use retrieved passages as source evidence; INT16 teaching plans can attach authorized passages to the existing curriculum context; INT19 and INT20 can consume the already generated answer and citations for narration or display; INT21 and INT22 can use only explicit summaries or page citations returned for the current student. This branch does not merge or import those worktrees.

## Database and future migration reconciliation

INT-23 adds no SQLAlchemy tables or columns, so it adds no Alembic revision. Existing source migrations form one linear chain through `0010_mission_completions`. No database was migrated during implementation.

When INT17 and INT21 are integrated, first inspect `alembic heads` and `alembic history` after the code branches are combined. If they introduce parallel heads, create an Alembic merge revision whose `down_revision` contains every surviving head revision, then run upgrade and downgrade checks only against a newly created disposable PostgreSQL instance with pgvector available. If a later INT-23 change needs a table, create it from the actual integration merge head; do not guess the numeric revision or edit another branch's migration.

## Limitations

- Scanned/image-only PDFs are reported as text unavailable; OCR is not configured.
- Embedding and answer generation require the existing Gemini configuration. Automated tests mock providers.
- The quiz answer key is returned to the authenticated browser so it can grade the local attempt; it is a study aid, not a proctored assessment.
- The existing sessionStorage bearer-token design remains a platform-level limitation. The in-process request limit is per server worker; deployments with multiple workers should also enforce an edge/shared rate limit.
