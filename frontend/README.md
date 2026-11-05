# BHASHALEARN AI Frontend — FE-01

React + TypeScript + Vite foundation with React Router and a local FastAPI proxy.

## Prerequisites
Node.js 20.19+ or 22.12+ and npm.

## Start (Windows CMD)

```cmd
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and navigate to About. Use `npm run build` to validate TypeScript and production compilation.

During development `/api` requests are proxied to FastAPI at `http://127.0.0.1:8000`. Frontend environment variables beginning with `VITE_` are exposed to the browser: **never place API keys or secrets there**.

FE-01 is foundation only. Landing page, authentication, dashboard, classroom and voice will be implemented in later tasks.
