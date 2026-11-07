# ADV-03 - RAG teaching preparation

## Scope and status

This worktree adds a storage- and provider-independent tutoring orchestration
contract in `backend/app/services/rag_tutor.py`. It does not connect the
authenticated chat endpoint to retrieval, call a vector database, access private
documents, or claim that live RAG works. No database models or migrations were
added.

The current chat route in `backend/app/api/tutor.py` authenticates a student and
uses `owned_session(session_id, student, db)` before it builds the existing
Gemini request and persists the turn. A future integration should invoke RAG
only after that ownership check and should preserve the existing provider
failure behavior (no partial chat turn persisted).

## ADV-02 adapter contract required

ADV-02 can provide a small adapter implementing the `PassageRetriever` protocol
from `backend.app.services.rag_tutor`:

```python
class PassageRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...
```

The request fields are:

- `student_id`: the authenticated student ID, supplied by the API boundary;
- `query`: the student's current question;
- `topic`: the owned learning session's topic;
- `limit`: requested maximum (currently 5).

The result is `RetrievalResult(passages=tuple[RetrievedPassage, ...])`. Every
passage must carry `passage_id`, `document_id`, `student_id`, `document_title`,
one-based `page_number`, plain `text`, and a numeric `score`. Scores must be
normalized so larger means more relevant; the current orchestration default
acceptance threshold is `0.35`. Retrieval must apply owner filtering in its
storage query using the request's `student_id`, and must return only pages from
documents owned by that student. The service independently rejects any result
whose student ID differs from the authenticated ID. The adapter must not expose
storage keys, filesystem paths, other students' document metadata, or raw
database/vector records.

The existing ADV-01 `Document` / `DocumentPage` models contain the owner ID,
document ID, filename, page number, and extracted text. ADV-02 should map its
chunk metadata back to this source metadata. Chunking and vector schema are
intentionally unspecified here because ADV-02 is still in progress.

## Orchestration and citations

`orchestrate_tutoring(...)` takes the authenticated student ID, the already
verified session owner ID, question, topic, language, level, a retriever, and a
generator callback. It checks session ownership before retrieval, asks the
retriever with that same student ID, rejects cross-owner passages, drops weak
or blank matches, and caps context to five passages. The generator contract is
`Callable[[GenerationRequest], GeneratedAnswer]`. Its response contains answer
text and zero or more citation IDs (`S1`, `S2`, ...). Inline markers are also
recognized. Only IDs tied to selected passages are kept; unknown markers are
removed. The returned `TeachingResponse` contains the answer, citations,
whether any retrieval was used, and whether the answer cited retrieved evidence.

Retrieved text is inserted as JSON-encoded user data, while the system
instruction explicitly treats it as untrusted evidence and forbids following
embedded instructions. The system instruction requests Telugu Unicode for
Telugu words, retains useful English technical terms, and avoids Romanized
Telugu. For empty or low-relevance retrieval, the generator receives an
explicit general-knowledge fallback notice and no document citation is added.

Citation attribution verifies that a citation names a result returned for this
student; it cannot prove that every generated factual claim is supported. A
production provider integration should preserve the citation-ID contract and
add provider-specific output parsing/grounding evaluation as needed.

## Dependencies and pending integration

- ADV-02 must finish and publish a stable retrieval adapter over private
  document chunks, with owner-filtered search and source metadata.
- Confirm the retrieval score scale and tune `DEFAULT_MIN_SCORE` against real,
  appropriately authorized evaluation data before enabling retrieval.
- A future integration must inject a concrete retriever and adapt the existing
  Gemini client to `GenerationRequest` / `GeneratedAnswer`.
- The authenticated tutor route must call orchestration only after its existing
  session ownership check, return citation metadata in its API response, and
  persist the final formatted assistant answer consistently.
- Add integration tests only after ADV-02's API is merged and available. This
  preparation intentionally adds no migration, real retrieval, or DB-writing
  test.

## Independent verification

Run the mocked contract tests from the repository root:

```cmd
python -m pytest -q backend\tests\test_rag_tutor.py
```

These tests use in-memory fake retriever and generator objects and do not
connect to PostgreSQL, pgvector, document storage, or Gemini.
