# INT-24 AI Browser Research & Task Agent

## Current capability boundary

The authenticated `/research` workspace searches public web metadata with the documented Brave Search API when `BHASHALEARN_BRAVE_SEARCH_API_KEY` is configured. It calls only `https://api.search.brave.com/res/v1/web/search`, caps queries and results, does not follow redirects, and does not fetch arbitrary result pages. Without credentials it selects `offline_demo` and shows fixed educational fixture sources; the UI labels these as an offline demonstration. With both Brave Search and the existing `BHASHALEARN_GEMINI_API_KEY`, Gemini creates an optional bilingual synthesis from bounded excerpts. The response is JSON-validated and citations must point to returned source indices. Invalid AI output falls back to clearly labeled excerpt-based study framing.

Each source stores its title, canonical HTTP(S) URL, publisher host, retrieval time, and bounded provider excerpt. Duplicate canonical URLs within a session are discarded. A domain-based quality note identifies selected `.edu`, `.gov`, Khan Academy, and OpenStax hostnames; other sources are marked unassessed. This is not a credibility score or content verification. Findings point to source indices, and uncertainties state that excerpts are not independent verification. The UI labels model output as AI interpretation and source excerpts as evidence. Source content is JSON-quoted as untrusted evidence and explicitly cannot override system instructions; it is never executed.

## API

- `POST /api/v1/research/sessions` creates an authenticated student-owned draft.
- `POST /api/v1/research/sessions/{id}/run` executes bounded search and saves source excerpts, citations, and summary.
- `GET /api/v1/research/sessions` and `GET /api/v1/research/sessions/{id}` list history and retrieve findings/citations.
- `POST /api/v1/research/sessions/{id}/study-plan` creates a bounded two-week review plan.
- `POST /api/v1/research/tasks` prepares an idempotent task proposal; `GET /api/v1/research/tasks` reads the approval queue.
- `POST /api/v1/research/tasks/{id}/request-approval`, `/approve`, and `/cancel` manage the scoped approval state.
- `GET /api/v1/research/audit` returns minimal task event history.

Task proposals accept only resource lists, course comparison plans, study checklists, email drafts, and reminder proposals. Approval expires after 15 minutes and applies only to that owned task. No browser automation provider is installed, so tasks remain non-executable; approval records intent and never submits, sends, registers, books, purchases, or shares data.

## Security and limits

No arbitrary webpage fetch, download, or redirect is implemented. URL validation rejects unsupported schemes, userinfo, localhost, local suffixes, and private or non-global IP literals. Live source hostnames are resolved and rejected if any resolved address is non-public before a citation is saved. Provider requests use a fixed HTTPS origin, an 8-second timeout, no redirects, 5 displayed results (8 maximum adapter results), 500-character query bounds, and a per-student process-local rate limit. The provider key is read only from server configuration and is never returned or logged. The simple process-local limiter should be supplemented by a shared edge limit in multi-worker deployments.

## Persistence and integration

Revision `0011_int24_research` follows source HEAD `0010_mission_completions`. It creates student-owned research sessions, source citations, task proposals, and minimal audit events. No migration has been run on a configured/shared database.

The source and INT24 branches develop independently from the verified source commit. INT17 has two branch-local revisions based on `0010`, and INT21 has two branch-local revisions based on `0010`; INT24 also adds its own child revision. INT20 and INT22 integration must inspect their actual revision graphs when those branches are reconciled. After merging feature code, create a merge revision whose `down_revision` lists every surviving head discovered with `alembic heads` and `alembic history`; do not renumber or rewrite feature revisions. Verify upgrades and downgrades only on a newly created disposable PostgreSQL database.

`research_adapters.py` defines optional typed seams for INT16 teaching intelligence, INT17 personal assistant, INT21 career roadmap, INT22 command center, and INT23 Knowledge Studio. All default to `None`; this branch imports no independent feature implementation. INT23 currently has no migration; inspect its eventual integrated model graph before authoring any merge migration.
