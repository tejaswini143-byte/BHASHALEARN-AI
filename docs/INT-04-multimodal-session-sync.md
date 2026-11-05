# INT-04: Multimodal Session Synchronization

## Architecture

Chat, Voice, and Visual use one authenticated `learning_sessions.id`. Chat and Voice continue to send student turns through `POST /api/v1/tutor/sessions/{session_id}/chat`; voice transcription itself does not write a conversation message. The existing chat message table remains the single conversation store, and tutor history stays bounded and chronological.

`GET /api/v1/sessions/{session_id}/context?limit=100` returns the owned session topic, current student language/level/goal preferences, recent messages, and the selected built-in visual lesson description. The endpoint caps `limit` at 500. `PUT /api/v1/sessions/{session_id}/visual-context` saves an allowlisted visual key and optional graph endpoints. Both endpoints require bearer authentication and enforce session ownership.

The existing Visual Studio includes a fraction-bars view and the Dijkstra graph lesson. Its selection and graph endpoints are persisted in `session_visual_states`, scoped one-to-one to a learning session. Gemini receives only the bounded, server-authored text description for the selected lesson; it is told that the description is data and that no image was supplied. No image is uploaded to Gemini. Selecting or revisiting a mode does not create chat messages.

Mode links carry `?session=<id>`. Chat, Voice, and Visual load the authenticated context when opened. Explicit unknown or unauthorized session IDs are not silently replaced by another session. On the legacy standalone routes without an ID, Chat/Voice retain their existing first-session choice; Visual selects the first owned session and directs the student to create one if none exists.

Language changes in Chat, Voice, or Visual update the existing student preference record; the same session and history remain. Language and learning level/goal are read from that shared record and supplied to the existing Gemini tutor. No new state-management library or provider client was introduced.

## Database

Migration `0005_session_visual_state` follows `0004_learning_memories`. It creates `session_visual_states` with a session primary key and cascading foreign key, allowlisted key, optional Dijkstra start/end nodes, and update timestamp. Apply it with the project's normal local development migration command:

```cmd
python -m alembic -c backend\alembic.ini upgrade head
```

Confirm the target is the local development database before applying migrations. No production database was accessed by this implementation.

## Verification

Backend regression tests:

```cmd
python -m pytest -q backend\tests\test_multimodal_context.py
python -m pytest -q backend\tests
```

Frontend production build:

```cmd
cd frontend
npm.cmd run build
```

Manual browser acceptance: sign in, open one owned session, send a chat turn, switch to Voice and submit a transcript, switch to Visual and select/view a lesson, return to Chat, and ask about the visual description. Confirm the same session ID is in each mode URL and the same ordered conversation is present. Change language, refresh Visual, and confirm topic, preference, lesson selection, and Chat context remain. Open a second session and confirm its visual selection is separate. Verify a different student's token receives 404 for another student's session context.

## Limitations

- Visual state is limited to two built-in lessons: equivalent-fraction bars and the Dijkstra graph. It does not persist arbitrary lesson content, quiz progress, animation position, or image data.
- The selected visual lesson is represented to Gemini by a small trusted textual description, not by pixels or a browser screenshot.
- Preference changes are student-wide because the existing preference model is student-scoped, not session-scoped.
- No live provider/browser verification is implied by this document; report only results actually run in the current environment.
