# INT17 assistant architecture

## Foundation and ownership

INT17 adds the assistant on the `0010_mission_completions` baseline with Alembic revisions `0011_int17_assistant` and `0012_int17_provider_integrations`. FastAPI bearer authentication resolves a server-side `Student`; every assistant query and mutation is scoped by that authenticated student ID. The client never supplies an owner identifier. Stored instants are UTC and settings carry an IANA timezone.

## Providers and data flow

- `backend/app/services/assistant_providers.py` contains Google OAuth/API, Fernet token encryption, Twilio Voice/Verify, and signed callback adapters. `assistant_google.py` bounds Gmail synchronization, keeps only message headers and a 1200-character excerpt, extracts candidate dates for user confirmation, and manages Calendar records.
- Gmail requests `openid`, `email`, `gmail.readonly`, and `gmail.send` scopes. Calendar requests `openid`, `email`, and `calendar.events.owned`. Gmail sending is a separate operation even though the token includes its explicit send scope. OAuth uses random state, PKCE S256, ten-minute expiry, one-time state consumption, and an HTTPS deployment redirect URI.
- A generated reply uses the configured Gemini key, places mailbox text in an untrusted data block, and becomes a draft. Every send needs draft approval and a separate send action. High-risk drafts are rejected by the send route. Gmail has no client idempotency key, so the draft is durably moved to `sending` before the provider request; ambiguous outcomes become `send_uncertain` and are not blindly retried.
- Reminder calls require production mode, both global and telephony enable switches, complete credentials, a verified phone, explicit call consent, unpaused settings, and quiet-hours clearance. A durable call attempt is written before the provider request. Ambiguous call outcomes are not retried. Twilio callbacks are checked against the configured public callback URL and signature, account, destination, Call SID, and monotonic sequence number. Telugu uses the configured Twilio `te-IN` voice; mixed reminders use a fixed Telugu suffix.
- Background work is persisted in `assistant_jobs`. A separate worker claims jobs via PostgreSQL `FOR UPDATE SKIP LOCKED` (and conditional updates on SQLite), retries sync/provider failures with bounded backoff, and recovers stale claims conservatively. It must use the same dedicated database as the API. Test invocations default to mock-only.

## API surface

All routes are mounted under `/api/v1/assistant` and require an authenticated user except the provider callback endpoints:

- `/settings`, `/deadlines`, `/deadline-candidates` manage profile, manual reminders, and explicit confirmation for extracted dates.
- `/integrations/{gmail|calendar}/connect`, callback, sync, and delete control OAuth and synchronization.
- `/emails`, `/emails/{id}/draft`, `/drafts/{id}` and approve/reject/send implement email review and explicit sending.
- `/phone/verification/*`, `/calls`, and the signed Twilio status webhook manage consented calls and their history.
- `/calendar/events` syncs events and accepts confirmed user-requested event creation.
- `/voice/commands`, `/voice/transcribe`, and `/voice/speech` accept authenticated text/voice requests. Mutating commands require confirmation; speech uses the existing Gnani adapters.
- `/activity` exposes the user's audit trail.

## Environment and deployment

Provider features default off in every environment. Set only in a protected production secret store:

| Variable | Purpose |
| --- | --- |
| `BHASHALEARN_ASSISTANT_TOKEN_ENCRYPTION_KEY` | Fernet key for OAuth access/refresh tokens. Generate with Python `cryptography.fernet.Fernet.generate_key()` and protect/back up separately. |
| `BHASHALEARN_ASSISTANT_PUBLIC_BASE_URL` | Public application origin for the OAuth completion redirect. |
| `BHASHALEARN_GOOGLE_OAUTH_CLIENT_ID`, `BHASHALEARN_GOOGLE_OAUTH_CLIENT_SECRET`, `BHASHALEARN_GOOGLE_OAUTH_REDIRECT_URI` | Google Cloud OAuth web client; register the exact callback URL. Enable Gmail and Calendar APIs. |
| `BHASHALEARN_ASSISTANT_GOOGLE_LIVE_ENABLED` | Explicit Google integration switch; requires `BHASHALEARN_ASSISTANT_LIVE_OPERATIONS_ENABLED=true`. |
| `BHASHALEARN_TWILIO_ACCOUNT_SID`, `BHASHALEARN_TWILIO_AUTH_TOKEN`, `BHASHALEARN_TWILIO_FROM_NUMBER`, `BHASHALEARN_TWILIO_VERIFY_SERVICE_SID` | Twilio Voice and Verify credentials/resources. |
| `BHASHALEARN_TWILIO_STATUS_CALLBACK_URL` | Exact public HTTPS webhook URL configured in Twilio. |
| `BHASHALEARN_TWILIO_ALLOWED_DESTINATION_PREFIXES` | Required comma-separated E.164 country calling prefixes reviewed for the Twilio account's enabled regions (for example, a narrowly approved `+1`). Live calls remain unavailable when empty or malformed. |
| `BHASHALEARN_TWILIO_LIVE_CALLS_ENABLED` | Explicit Twilio switch; also requires global live-operation switch and production environment. |
| `BHASHALEARN_ASSISTANT_MAX_CALLS_PER_DAY` | Per-user rolling 24-hour call cap, 1–20 (default 3). |
| `BHASHALEARN_GEMINI_API_KEY`, `BHASHALEARN_GEMINI_MODEL` | Optional contextual reply drafting. Email excerpts and user response points are sent to Gemini when drafting is explicitly requested. |
| `BHASHALEARN_GNANI_*` | Existing Gnani Prisma/Timbre credentials for optional speech input/output. |

Apply migrations on the deployment database after a backup and run `python -m backend.scripts.assistant_worker` as an independent process. Do not point local tests at an existing shared database. Live calls, OAuth callbacks, Gmail, Calendar, Gnani speech and real email sending were not exercised in development. Before production activation, validate Google OAuth verification/consent-screen requirements and review each allowed Twilio destination prefix against the account's regional permissions and applicable calling requirements. There is no auto-reply rules engine; automatic sending is intentionally disabled.
