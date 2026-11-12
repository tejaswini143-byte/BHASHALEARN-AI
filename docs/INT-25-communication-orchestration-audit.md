# INT-25 Gmail, Calendar, and Phone Orchestration — Gap Audit

**Audit date:** 2026-11-08  
**Source baseline:** `feature/unified-ai-classroom` at `70154c7fbd591a67c72805e4c36ab06058399c47`  
**INT17 worktree:** `C:\Users\Tejaswini\BHASHALEARN-INT17`, branch `feature/int-17-personal-assistant`  
**INT17 state:** dirty and actively changing. At final read-only check it had six modified tracked files and 20 untracked files (including the implementation, docs, tests, and generated test-result artifacts; Git status groups some under directory entries). Its `HEAD` is the same baseline commit, so the capabilities below are observations of uncommitted files and are not present in the INT17 branch commit. Do not treat this as a reproducible release or merge-ready implementation.  
**INT24 state:** dirty and actively changing too. At final read-only check, `backend/app/config.py`, `backend/app/db/models.py`, and `backend/app/main.py` were modified, while `backend/alembic/versions/0011_int24_research.py`, `backend/app/api/research.py`, and `backend/app/services/research.py` were untracked. Inspected read-only.

## Decision and scope

INT25 is limited to this verified gap audit and integration contract. INT17 already contains a substantial, active implementation of the same provider workflows. A second provider/workflow implementation would duplicate active work and would depend on uncommitted code, so INT25 adds no runtime adapter, endpoint, frontend, migration, credentials, or provider registration. Revisit implementation after INT17 stabilizes and its integration contract is agreed.

The classifications below describe code observed in INT17's dirty worktree. “Implemented” means a concrete path exists in that worktree; it does **not** mean it was executed successfully. No INT17 or INT24 test suite, production build, Playwright suite, provider call, or migration was run during this audit.

## INT17 capability audit

| Capability | Status | Read-only evidence and gap |
|---|---|---|
| Gmail connection | Partial | `/integrations/gmail/connect`, callback, sync, disconnect, per-student account records and explicit feature switches exist. Live OAuth is configuration-gated and has not been exercised. |
| OAuth callback and token storage | Partial | One-time, expiring, student-bound OAuth state, PKCE S256 and encrypted access/refresh token fields exist. Callback validates state and returned scopes. Key rotation/versioned re-encryption is not implemented; changing the Fernet key can make stored tokens undecryptable. |
| Email metadata reading | Implemented | Bounded Gmail metadata sync stores sender, subject, snippet and dates; it does not fetch full message bodies. |
| Email draft creation and preview | Implemented | Draft API and email-reply generation persist recipient, subject, body and risk category; the UI renders and edits drafts before send. Static code only. |
| Email sending approval | Partial | Separate approve and send routes require approval, check granted `gmail.send`, and automatic sending is disabled. Approval is a mutable draft status/timestamp, without an immutable payload digest or expiry. High-risk sends are rejected. |
| Email exactly-once behavior | Partial | `Idempotency-Key`, a persisted `sending` state, and an `send_uncertain` outcome prevent blind retry after ambiguous Gmail responses. Gmail itself has no idempotency key, so end-to-end exactly-once delivery cannot be guaranteed; recovery requires mailbox inspection. |
| Calendar availability | Partial | Upcoming primary-calendar events are read and cached. No free/busy query or authoritative availability computation is implemented. |
| Calendar event proposals | Partial | Voice commands can return a preview requiring confirmation. There is no durable proposal/approval record binding all event fields and an expiration. |
| Calendar event creation | Partial | A `confirmed` flag is required and deterministic IDs/dedupe keys support duplicate recovery. No conflict check is made before creation; edit/delete workflows are absent. |
| Phone provider integration | Partial | Credential-gated Twilio Voice and Verify adapters exist. Live mode requires production and explicit switches. Tests are mock oriented; the provider is not verified/configured by this audit. |
| Outbound-call approval | Missing | Reminder jobs can place calls after global consent, verification, pause and quiet-hour checks. There is no explicit approval bound to each exact call payload immediately before execution. |
| Voice-command parsing | Partial | English/Telugu keyword parsing supports a narrow set of inbox, deadline, email draft and calendar intents. It is not a general intent parser and does not use a shared proposal state machine. |
| Consent and quiet hours | Partial | Phone verification, explicit SMS consent, call-consent timestamp, pause switch, timezone-aware quiet hours, and per-user call caps exist. Per-call approval and explicit AI-assisted-call disclosure are missing or not evidenced. |
| Audit logging | Implemented | Student-scoped assistant audit rows are written for settings, OAuth, draft/send, calendar and call activity. Retention configuration exists; verified cleanup/retention enforcement was not established. |
| Idempotency | Partial | Unique student-scoped keys cover jobs, calls, email sends and calendar dedupe. They are separate domain safeguards, not a unified approval/execution ledger. |
| Token encryption and rotation | Partial | Fernet encryption/decryption and OAuth refresh-token use exist. No key versioning or rotation migration is present. |
| Provider errors and retries | Partial | Provider errors are generally translated to stable codes and job retries use bounded backoff; ambiguous side effects are treated conservatively. Runtime behavior and all redaction paths are unverified. |
| Shared approval state machine | Missing | No common `proposed → awaiting approval → approved → executing → completed/failed/cancelled` record with exact action payload, authenticated student, approval expiry, and replay protection was found. |
| Frontend communication UI | Partial | The uncommitted `AssistantDashboard` shows connected-account status, email previews/review, call history/activity, and provider errors. The inspected implementation does not establish a complete shared approval queue, calendar proposal/conflict UI, or phone-call proposal UI. |

### Relevant INT17 surface observed

All assistant routes are intended under `/api/v1/assistant` and use the existing bearer `current_student` dependency except the signed Twilio callback. Observed route groups include:

- `/settings`, `/deadlines`, `/deadline-candidates`
- `/integrations`, `/integrations/{gmail|calendar}/connect`, callback, sync and disconnect
- `/emails`, `/emails/{id}/draft`, `/drafts`, approve/reject/edit/send
- `/calendar/events`
- `/phone/verification/*`, `/calls`, `/webhooks/twilio/status`
- `/voice/commands`, `/voice/transcribe`, `/voice/speech`
- `/activity`

INT17 proposes Alembic revisions `0011_int17_assistant` and `0012_int17_provider_integrations`. They were untracked in the inspected worktree and were not applied. No database was touched.

## Integration contract for follow-on work

### Typed provider boundary

Keep INT17 as the owner of provider implementations after it stabilizes. Formalize its procedural functions behind typed ports (Python `Protocol` or equivalent) without adding another OAuth/token store. Recommended minimum contract:

- `GmailProvider`: `list_metadata(student_id, cursor) -> MetadataPage`, `create_draft(student_id, EmailDraft) -> DraftRef`, `send_approved(student_id, ApprovedAction, idempotency_key) -> SendResult`, `revoke(student_id) -> None`.
- `CalendarProvider`: `list_events(student_id, window) -> list[CalendarEvent]`, `get_availability(student_id, window) -> Availability`, `create_event(student_id, ApprovedAction, idempotency_key) -> CalendarEvent`, `update_event(...) -> CalendarEvent`, `revoke(student_id) -> None`.
- `PhoneProvider`: `verify_destination(...)`, `place_call(student_id, ApprovedAction, idempotency_key) -> CallRef`, and `verify_callback(raw_request) -> VerifiedCallEvent`. Production implementation must remain disabled until the provider and callback URL are explicitly configured and verified. The INT17 Twilio implementation is a candidate, not a verified live integration.

Every provider method receives a server-derived student identity or an already owner-scoped connection; clients never select another student's provider account. Provider errors exposed to the UI use stable redacted codes, not provider bodies, tokens, phone numbers, email contents, or credentials.

### Approval and execution boundary

Use a single durable action record owned by the existing authenticated `Student`, with fields equivalent to `action_id`, `student_id`, `action_type`, canonical payload, payload digest, state, `created_at`, `expires_at`, `approved_at`, `executed_at`, idempotency key, and redacted result/error code. Approval must compare the current canonical payload digest to the digest shown in the preview and reject expired, changed, consumed, or cross-student approvals. Claim `approved → executing` transactionally before calling an external provider. Never blindly retry ambiguous Gmail or phone outcomes.

### OAuth and API security

Reuse `POST /api/v1/auth/login`, bearer JWT validation, and `current_student` from `/api/v1/auth/me`; do not introduce a second student identity/session. Keep provider OAuth state random, single-use, expiring, bound to the requesting student/provider, and PKCE protected. Keep Gmail and Calendar scopes separate and as narrow as the requested actions allow. Encrypt refresh/access tokens at rest, support an explicit key-rotation procedure, redact logs, and revoke provider grants on disconnect. Apply rate limits to OAuth starts, sync, email operations, phone verification, and provider callbacks. Retain only necessary metadata and define/enforce cleanup.

### Product integrations

- **INT17 personal assistant:** it owns communication domain models, OAuth, provider adapters, action approvals, and communication API routes. INT25 should extend/reuse those contracts after INT17 commits them; it should not duplicate those systems.
- **INT22 student dashboard:** mount the assistant as an authenticated dashboard module/route and pass the existing bearer session through the established API client. Keep provider credentials and student IDs out of browser storage and request payloads. The route/component wiring observed in INT17 is uncommitted and needs an agreed merge point.
- **INT24 research agent:** research tasks already expose a related student-owned proposal/approval/audit vocabulary in INT24's dirty worktree. Keep research approvals scoped to research actions; share only a stable approval UI/API contract if agreed. Do not couple communications to INT24 tables or import its uncommitted implementation.
- **Existing session APIs:** use authenticated `/api/v1/auth/*` and the established student bearer session. Voice commands may be an entry point, but all communication side effects must route through the same durable preview/approval/execution contract.

## Required follow-up before implementation can be considered complete

1. Stabilize and commit INT17, then rerun its test suite against disposable resources and reconcile the gaps above with the final code.
2. Add a durable immutable-payload approval record with expiry and per-call approval; bind draft approval to recipient, subject and body version.
3. Add Calendar free/busy conflict checks and durable proposal/confirmation for create/update operations, including timezone validation and daylight-saving behavior.
4. Define executable typed provider protocols and test them against no-network mocks. Verify the live provider, scope grants, revocation and callback configuration administratively before enabling production.
5. Add explicit AI-assisted-call disclosure, signed callback replay coverage, rate-limit tests, retention cleanup, token key rotation, and frontend proposal/approval workflows.
6. Run requested backend isolation/OAuth/encryption/approval/idempotency/conflict/consent/webhook/retry tests, frontend unit tests, production build, Playwright approvals, and disposable migration tests only after the owning implementation is stable. Never use real provider side effects in tests.

## Verification record

- Source branch and HEAD matched the requested values before worktree creation.
- INT25 branch and target path were absent before worktree creation; INT25 was created from the verified source HEAD.
- INT17 and INT24 were inspected read-only; both were dirty. No tests were run against them because test execution could create artifacts in those other worktrees and would validate uncommitted code.
- No real-provider calls, emails, events, phone calls, OAuth registrations, token changes, database changes, or migrations were performed.
- This deliverable is an audit document only; runtime tests/build are not applicable and remain outstanding for the eventual implementation.

