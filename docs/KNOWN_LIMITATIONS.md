# Known limitations and verification gaps

- The candidate has no authoritative INT-01 through INT-30 ticket-to-scope mapping. This work records only repository-confirmed IDs and leaves the rest unmapped.
- This QA run uses deterministic browser mocks for registration, classroom tutoring, assistant chat, and PDF semantic-search display. It does not verify provider quality, credentials, network behavior, or live end-to-end provider calls.
- Live Gnani Prisma STT was not verified in this pass. The repository's voice architecture note also records no accepted live Prisma transcript. Historical Timbre POC results are not a current live acceptance.
- Live Gemini tutor and embeddings were not exercised. Deterministic fake embeddings are a testing aid and are not Gemini evidence.
- The full Playwright suite was not rerun here. Existing tests include opt-in database mutations and may skip unless a disposable database and synthetic accounts are explicitly configured.
- Backend pytest tests were not run in this pass. A working Python environment and an isolated database are needed for database-backed acceptance; no database is assumed safe by default.
- Audio device permission, microphone capture quality, browser autoplay, real network latency, and end-to-end Telugu/English transcription quality need separate live/browser verification.
- Playback-clock animation is an approximation when the provider supplies no validated viseme timeline. The synthetic teacher viseme demo is not a live speech result.
- PDF extraction does not imply OCR for scanned PDFs. Indexing/search sends extracted text and queries to the configured embedding provider only after explicit user action.
- Analytics surfaces only recorded evidence. Quiz-specific analytics remains unavailable until a provider adapter is connected, as described in `backend/INT14_ANALYTICS.md`.
- Career scenarios are deterministic practice/reflection flows and do not predict a learner's future.
- The frontend production build reports that the generated three.js vendor chunks exceed 500 kB. The build succeeds, but bundle-size optimization remains open.
