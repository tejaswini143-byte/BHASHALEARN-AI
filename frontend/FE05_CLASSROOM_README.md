# FE-05 — AI Classroom

## Features
- Protected `/classroom` route with responsive session sidebar, searchable conversation list, and mobile navigation.
- Create learning sessions and resume previous sessions from `/classroom?session=<id>`.
- Read saved messages from `GET /api/v1/sessions/{id}/messages`.
- Send text prompts to `POST /api/v1/tutor/sessions/{id}/chat`; the backend generates and persists both sides of the conversation.
- Tutor response history reloaded from backend after a successful turn; loading, failure, and empty states.
- Language selector updates `PUT /api/v1/students/me/preferences` for subsequent tutor responses.
- Dashboard links to the classroom and to individual sessions.

## Local verification
```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
git fetch origin
git switch feature/fe-05-ai-classroom
git pull origin feature/fe-05-ai-classroom
```
Run the FastAPI server from the repository root in one terminal and Vite from `frontend` in another. Run `npm run build` from `frontend`. Log in, open dashboard, choose **Open AI Classroom**, create a topic, send a prompt, refresh the browser, and confirm the messages persist.

## Backend requirement
The tutor calls the configured Gemini provider. Set `BHASHALEARN_GEMINI_API_KEY` securely in your backend environment; do not paste keys into chat or commit them. If the provider is not configured or fails, the UI displays the backend error and no successful tutor turn is claimed.

## Scope
This is a **text AI classroom**. Live microphone audio, speaking avatars, real-time pronunciation evaluation, visual lessons, and streaming responses are not implemented here. Language preference applies to the tutor's next responses, not to existing saved messages.
