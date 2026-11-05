"""BE-08 memory API tests using isolated SQLite."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'memory.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    def override_db():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()

def auth(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}

def test_memory_create_list_filter_delete(client):
    headers = auth(client, "one@example.com")
    url = "/api/v1/memories"
    created = client.post(url, headers=headers, json={"topic": "Greetings", "note": "  Needs Telugu examples  "})
    assert created.status_code == 201, created.text
    memory = created.json()
    assert memory["note"] == "Needs Telugu examples"
    assert len(client.get(url, headers=headers).json()) == 1
    assert len(client.get(url + "?topic=Other", headers=headers).json()) == 0
    assert client.get(url + "/" + memory["id"], headers=headers).status_code == 200
    assert client.delete(url + "/" + memory["id"], headers=headers).status_code == 204
    assert client.get(url, headers=headers).json() == []

def test_memory_student_isolation(client):
    first = auth(client, "first@example.com")
    second = auth(client, "second@example.com")
    url = "/api/v1/memories"
    memory_id = client.post(url, headers=first, json={"topic": "Private", "note": "Personal note"}).json()["id"]
    assert client.get(url, headers=second).json() == []
    assert client.get(url + "/" + memory_id, headers=second).status_code == 404
    assert client.delete(url + "/" + memory_id, headers=second).status_code == 404
    assert client.get(url).status_code == 401

def test_memory_validation(client):
    headers = auth(client, "valid@example.com")
    url = "/api/v1/memories"
    assert client.post(url, headers=headers, json={"topic": " ", "note": "hello"}).status_code == 422
    assert client.post(url, headers=headers, json={"topic": "A", "note": "  "}).status_code == 422
    assert client.get(url + "?limit=0", headers=headers).status_code == 422
