# BE-02 — PostgreSQL database foundation

The backend uses SQLAlchemy 2 ORM models and Alembic migrations.

## Local Windows CMD

From repository root, with your existing virtual environment active:

```cmd
python -m pip install -r backend\requirements.txt
python -m pytest -q backend\tests
```

For PostgreSQL, create an empty database named `bhashalearn` and set an environment variable (replace the password with your own):

```cmd
set "BHASHALEARN_DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/bhashalearn"
python -m alembic -c backend/alembic.ini upgrade head
```

For a local migration smoke test without PostgreSQL:

```cmd
set "BHASHALEARN_DATABASE_URL=sqlite:///./backend_be02_test.db"
python -m alembic -c backend/alembic.ini upgrade head
```

Do not commit a database password or real .env file. Run migrations against a disposable database first. The migration creates five tables: students, courses, learning_sessions, chat_messages, learning_progress.
