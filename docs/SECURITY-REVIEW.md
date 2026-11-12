# Security Review — Initial Audit

## Verified controls

- Student auth API exposes registration/login/me under `/api/v1/auth`; the frontend stores bearer token in `sessionStorage` and sends it through its API helper.
- Backend settings require explicit database/JWT configuration; no embedded database URL/default JWT secret is documented in INT-18B.
- Gemini is server-side, uses the `x-goog-api-key` header, and has a generic provider error response. The Gemini key is not a `VITE_*` frontend setting in the baseline docs.
- Recovery test accounts and data are synthetic per the historical Phase B report.

## Findings / outstanding review

- Current recovery `.env` database name is different from the authorized test target and its credentials fail authentication. Do not start another backend or make app writes until the exact target is restored and checked.
- Current key presence does not prove validity. The value remains local and was never exposed; no live request occurred.
- INT-20 adds a credential-readiness endpoint that reports configuration state without contacting Gnani. Voice request limits are process-local; they do not provide a distributed limit across multiple backend workers.
- No Gnani key is configured in the recovery/RC runtime. A non-placeholder `GNANI_API_KEY` is present in the original project's ignored POC-01/POC-02 local configuration; only variable presence was inspected, and the value was not exposed or validated. STT/TTS live-provider validation still requires explicit test approval; no current provider request was made.
- Route guards are frontend navigation controls; backend ownership checks remain the security boundary and need negative cross-student API acceptance tests.
- No comprehensive review has yet covered password policy, JWT expiry/revocation, CORS, rate limiting, CSRF/storage risks, logging redaction, upload scanning/limits, OAuth scopes, assistant action confirmation, dependency advisories, or production deployment settings.
- INT-17 assistant code is now selectively present in the RC. Gmail/Calendar/Twilio operations are disabled by default and the tests were run with live switches off. Email has a per-draft approve step and prevents editing an approved draft; calendar/voice-command creation requires explicit confirmation. Remaining gaps include a shared durable action approval record, phone-call per-action review, enforced retention cleanup, OAuth/provider rate limits, encryption-key rotation, PostgreSQL migration testing, and live provider behavior. No provider credentials were used or provider calls made.
- The INT-17 `cryptography>=42,<47` dependency is declared and installed as 46.0.7 in the RC private venv from an official PyPI wheel after matching its published SHA-256. Standalone app import, HTTP readiness, and the 228-test backend regression passed. This resolves the local runtime blocker; it does not replace dependency advisory review before release.
- Historical docs note an early loopback database credential in Git history; assess any deployed role separately. No credential rotation was performed.

No production security certification is implied.
