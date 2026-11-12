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

During development `/api` and `/health` requests are proxied to FastAPI at
`http://127.0.0.1:8000` by default. Set `BHASHALEARN_API_PROXY_TARGET` to use a
different local backend port; it is only read by the Vite config and is not
exposed to browser code. Frontend variables beginning with `VITE_` are exposed
to the browser: **never place API keys or secrets there**.

For example, in Windows CMD:

```cmd
set BHASHALEARN_API_PROXY_TARGET=http://127.0.0.1:8002
npm.cmd run dev -- --host 127.0.0.1
```

FE-01 is foundation only. Landing page, authentication, dashboard, classroom and voice will be implemented in later tasks.
