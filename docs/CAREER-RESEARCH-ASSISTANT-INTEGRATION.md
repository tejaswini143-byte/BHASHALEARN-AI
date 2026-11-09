# Career, Research, and Assistant Integration Contract

This branch is based on integration candidate commit `4d364d4746ff97356cf26bfefda09903b243831d`. Feature files are additive. The app router, dashboard, authentication, SQLAlchemy models, migrations, and central settings were intentionally left outside this branch's ownership.

## Router and UI wiring

- Register `backend.app.api.career.router`, `backend.app.api.research.router`, and `backend.app.api.assistant.router` in the API app factory under the existing `/api/v1` prefix.
- Add the Career Roadmap, Research Workspace, and Assistant Dashboard routes and navigation links in the frontend's shared router/dashboard. Keep existing routes intact.
- Provide `ResearchWorkspace` and `AssistantDashboard` components with the existing auth helper and API error contract. `CareerRoadmap` uses the existing course, lesson, assessment, and progress endpoints.

## Persistence and settings

- Reconcile the feature model classes referenced by the three routers and assistant worker with the shared SQLAlchemy model registry. Every row must carry an authenticated student owner, and every read/update/delete query must include that owner.
- Reconcile Alembic heads before adding a merge revision. Career and research each bring a branch-local `0011` revision based on `0010_mission_completions`; assistant persistence revisions must be included from INT17/INT25. Do not renumber existing revisions or run these migrations against a shared database before reviewing the merged graph.
- Add the assistant encryption/OAuth/Twilio and research provider settings used by the adapters to central settings. Defaults must leave all live providers disabled. Keep secrets server-side, and never expose provider credentials to frontend payloads.
- The research search adapter runs in `offline_demo` mode without Brave credentials; AI synthesis is optional. The assistant queue uses mock outcomes by default. Preserve these defaults in development and tests.

## External action boundary

Research task approval only records scoped intent; it does not execute browser actions. Assistant email send, calendar writes, SMS verification, and voice calls require explicit per-action consent/approval, provider readiness, ownership checks, and idempotency. Tests must use provider mocks and must not send real mail, messages, or invitations.

## API verification still required after wiring

Run the feature API suites after the shared model registry, migrations, settings, and router registration land. Those suites cover student isolation, approval transitions, expiry, idempotency, provider failure handling, and offline behavior. In this worktree, the committed shared baseline lacks the feature model classes and settings, so API-level tests cannot collect without changing shared files outside this feature's ownership.
