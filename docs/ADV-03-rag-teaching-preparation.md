# ADV-03 - RAG teaching integration

## Integrated behavior

The authenticated chat route `POST /api/v1/tutor/sessions/{session_id}/chat`
now uses ADV-02's in-process vector search through
`VectorPassageRetriever` in `backend/app/services/rag_tutor.py`. It verifies the
session with `owned_session` before retrieval and passes the authenticated
student ID to retrieval. The adapter checks for that student's ready index,
embeds the current question as `RETRIEVAL_QUERY`, calls `search_documents`,
and maps ADV-02 hits into typed passages and citations.

ADV-02 scores are cosine similarity in `[-1, 1]`, where larger is more
relevant. ADV-03 currently accepts scores at or above `0.35`, caps prompt
context to five passages, and drops blank text. The SQL search scopes chunks,
index state, generations, and documents to the same student; it selects only
the active ready generation for processed documents. Document deletion
cascades to index state, generations, and chunks.

The chat response retains `session_id`, `reply`, `language`, and
`learning_level`, and adds `citations`, `grounded`, and `retrieval_used`.
Each citation contains its generated citation ID, document ID/title, and
one-based page number. The assistant reply includes a Sources footer for only
the citation IDs it emitted that match retrieved results. Unknown citation
markers are removed. `grounded` is true only when the answer cites a valid
retrieved passage; this is citation validation, not a formal entailment proof.

When no ready student-owned index exists, no query embedding request is made.
When search returns no passage meeting the threshold, the existing Gemini tutor
answers from general knowledge with no document citation. If embedding or
generation fails, the endpoint returns an error before persisting either side
of the chat turn. Retrieved PDF text is JSON-encoded as user content and
explicitly marked as untrusted reference material in the system instructions.

## Score calibration and limitations

The `0.35` cutoff has the correct direction for ADV-02 cosine similarity, but
is still provisional. The mock tests verify mapping and cutoff behavior; they
do not measure retrieval quality on a representative authorized corpus. Tune
the cutoff with a reviewed evaluation set before treating it as calibrated.

Prompt instructions and citation-ID validation reduce citation fabrication,
but do not prove that every sentence is entailed by its cited page. Provider
output grounding should be evaluated separately before making stronger
grounding claims.

## Configuration and database prerequisites

ADV-02 migration `0008_document_embeddings` and pgvector are required in the
database used by the application. No migration was run for this integration.
Before PostgreSQL tests, a read-only check confirmed the isolated database was
at revision `0008_document_embeddings` with pgvector 0.8.7 and the dedicated
`bhashalearn_adv02` test role. The check also verified the required table
privileges. The tests used that isolated database only.

Search embeds the query through `GeminiEmbeddingProvider`; tutoring generates
the answer through the existing Gemini tutor. Live connectivity and configured
credentials were not tested. The embedding provider uses
`BHASHALEARN_GEMINI_EMBEDDING_API_KEY` when configured and falls back to
`BHASHALEARN_GEMINI_API_KEY`; answer generation uses the existing
`BHASHALEARN_GEMINI_API_KEY`.

## Verification performed

- RAG and chat-boundary tests use mocked providers, mocked vector-search
  results, and a fake database session.
- Backend suite excluding `test_database.py`: 134 passed. This includes all
  three PostgreSQL integration tests. The migration test module was excluded
  because migrations were prohibited. Other backend SQLite tests use pytest's
  isolated temp database.
- The focused PostgreSQL RAG test used synthetic student/document/page rows,
  deterministic embeddings, and a mocked answer generator. It verified page
  citation metadata, owner filtering, active-generation deactivation, document
  deletion, and no chat-message persistence after generation failure. Test
  cleanup and a separate read-only check confirmed zero synthetic rows remain.
- Frontend tests: 10 passed; production build succeeded.
- No real student PDFs, production credentials, shared development database,
  E2E database, or live Gemini endpoint were used.

Run the focused RAG tests with:

```cmd
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_rag_tutor.py backend\tests\test_rag_tutor_api.py
```
