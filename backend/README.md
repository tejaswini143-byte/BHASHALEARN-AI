# BE-01 — FastAPI backend foundation

This is the first backend task. It deliberately does not connect to PostgreSQL,
authenticate students, or call AI providers; those come in later BE tasks.

## Windows CMD setup

From the repository root:

```cmd
.venv\Scripts\activate
python -m pip install -r backend\requirements.txt
python -m pytest -q backend\tests
python -m uvicorn backend.app.main:app --reload
```

Visit http://127.0.0.1:8000/docs for the API documentation and
http://127.0.0.1:8000/api/v1/health for the health endpoint.

Expected health response:

```json
{"status":"ok","service":"bhashalearn-api"}
```

## Configuration

Copy `backend/.env.example` to the repository root `.env`, or set
`BHASHALEARN_*` environment variables. The application reads the current
working directory's `.env` file by default. Never commit secrets.

## Test scope

The BE-01 tests check health endpoints, OpenAPI metadata, and 404 behavior.
No external services or API keys are required.
