# Feature 3 — Phase 2 backend persistence slice

Added a student-owned `FutureSeekerReflection` model and authenticated POST/GET/DELETE endpoints at `/future-seeker/reflections` (under the configured API prefix). Requests enforce a versioned, allowlisted, bounded `illustrative-simulation` payload. List and delete are scoped to the authenticated student. Nothing updates verified skills or career goals.

**Deployment blocker:** the existing Alembic migration chain's current head was not established through the GitHub file connector, so no speculative migration was committed. Production databases must receive a reviewed Alembic migration for `future_seeker_reflections` before these endpoints are used. Do not deploy this backend change until migration is authored and tested.

**Verification:** run `python -m pytest -q backend/tests/test_feature3_future_seeker.py`, then the backend suite. The GitHub connector cannot run the tests. Frontend saving UI, end-to-end API tests, migrations, and release acceptance are still pending. Do not call Phase 2 production-ready.
