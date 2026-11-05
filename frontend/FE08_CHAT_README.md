# FE-08 — Advanced AI Chat Workspace

## What's new
- A distinct **light-themed** chat interface at `/chat`, separate from the dark AI Classroom and Voice Studio.
- Dark searchable conversation sidebar, new session form, persisted chat history, message bubbles, suggested prompts, copy assistant reply, mobile layout.
- Uses existing authenticated session and tutor APIs; requires a configured Gemini backend for AI replies.
- Dashboard now prominently displays **Voice Studio**, **Visual Studio**, and **Advanced Chat** as separate clickable experience cards. The improved dashboard is inherited from the FE-07 branch.

## Run on Windows
```cmd
cd C:\Users\Tejaswini\BHASHALEARN-AI
git fetch origin
git switch feature/fe-08-advanced-chat
git pull origin feature/fe-08-advanced-chat
cd frontend
npm install
npm run build
npm run dev
```
Start backend separately from the repository root with `python -m uvicorn backend.app.main:app --reload`. Sign in and open `http://localhost:5173/dashboard`. Check the **Choose your experience** cards. Open `/chat`, create a topic, send a prompt, and refresh to verify persistence.

## Limitations
- No file uploads, RAG retrieval, streaming tokens, or server-side quizzes in this frontend task.
- Live Gemini connectivity and browser tests are not verified by the GitHub commit; check them locally.
- Dashboard metrics still come from the backend, not fabricated demo numbers.
