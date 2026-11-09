# GNANI submission handoff

## Scope and evidence

This work adds QA acceptance coverage and submission material on a separate worktree. It does not change application code. The candidate HEAD used to create this worktree was `4d364d4` (`fix: keep integrated dashboard navigation reachable`).

Confirmed GNANI references and current evidence are documented in `ADV-06-voice-architecture.md`, `FE06_VOICE_README.md`, and the POC folders. The repository records official Prisma/Timbre request-contract references and historical Timbre live WAV generation. It does not establish current live Prisma acceptance, a complete voice classroom live acceptance, or extra submission rules beyond the recorded material. No new GNANI requirements are inferred here.

## QA work included

- Mock-backed Playwright acceptance for registration → login → protected dashboard.
- Mock-backed classroom acceptance for a bilingual question and persisted user/assistant exchange.
- Mock-backed assistant workspace acceptance for saved bilingual conversation history.
- Mock-backed PDF semantic-search acceptance with document and page citation display.
- Submission docs: architecture summary, QA setup, feature acceptance matrix, video script, screenshot checklist, known limitations, and this handoff.

Existing test files cover authentication, dashboard navigation, teacher selection and controls, voice/avatar playback states, PDF extraction/indexing, quizzes, analytics, and the career scenario. The matrix names these suites and states the actual provider/database boundaries.

## Execution evidence

- `npm.cmd ci`: completed; audit reported 0 vulnerabilities.
- `npm.cmd test`: **64 passed, 0 failed**.
- `npm.cmd run build`: **passed**; Vite emitted a chunk-size warning for three.js vendor bundles above 500 kB.
- Playwright `submission-acceptance.spec.ts`: **4 passed, 0 failed** with mock API responses.
- Existing mock-driven browser suites for teacher, immersive controls, voice/avatar, quizzes, analytics, Future Me, visual lessons, missions, memories, and personalized teaching: **31 passed, 0 failed**.
- A sandbox write restriction prevented the first browser run from creating the Vite cache and report in this requested sibling worktree. The Playwright run proceeded only after requesting elevated execution for those temporary writes.
- Backend pytest, full Playwright suite, database mutations, and live Gemini/Gnani calls were not run.

## Remaining sign-off

1. Run DB-backed browser and backend tests only after verifying a disposable database, synthetic accounts, and separate test storage.
2. Obtain the authoritative INT-01–INT-30 acceptance mapping and evaluate currently unmapped IDs against it.
3. Record live Gnani Prisma/Timbre and Gemini evidence only in an authorized environment; otherwise keep the corresponding capabilities marked unverified.

See `FEATURE_ACCEPTANCE_MATRIX.md`, `KNOWN_LIMITATIONS.md`, and `QA_SETUP.md` for the detailed mapping and reproducible setup. This handoff does not claim all INT-01–INT-30 requirements or live providers are accepted.
