"""BE-03 authentication integration tests with isolated SQLite."""
from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'auth.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def register(client, email="Student@Example.com", password="safe-test-password-123"):
    return client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Telugu Learner", "password": password,
    })


def test_register_login_and_me(client):
    created = register(client)
    assert created.status_code == 201, created.text
    assert created.json()["email"] == "student@example.com"
    assert "password_hash" not in created.json()
    token_response = client.post("/api/v1/auth/login", json={
        "email": "student@example.com", "password": "safe-test-password-123",
    })
    assert token_response.status_code == 200, token_response.text
    token = token_response.json()["access_token"]
    assert token_response.json()["token_type"] == "bearer"
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["id"] == created.json()["id"]


def test_duplicate_email_and_wrong_password(client):
    assert register(client).status_code == 201
    assert register(client, email="student@example.com").status_code == 409
    response = client.post("/api/v1/auth/login", json={"email": "student@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_protected_route_rejects_missing_and_invalid_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_registration_validation(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    response = client.post("/api/v1/auth/register", json={
        "email": "a@example.com", "display_name": "   ", "password": "valid-password-123",
    })
    assert response.status_code == 422


def configure_reset_email(monkeypatch):
    monkeypatch.setenv("BHASHALEARN_SMTP_HOST", "mail.example.test")
    monkeypatch.setenv("BHASHALEARN_SMTP_FROM_EMAIL", "noreply@example.test")
    monkeypatch.setenv("BHASHALEARN_APP_PUBLIC_BASE_URL", "https://learn.example.test")
    from backend.app.config import get_settings
    get_settings.cache_clear()


def test_password_reset_is_one_time_and_updates_password(client, monkeypatch):
    assert register(client).status_code == 201
    configure_reset_email(monkeypatch)
    sent = []
    monkeypatch.setattr("backend.app.api.auth.send_password_reset_email",
                        lambda _config, recipient, url: sent.append((recipient, url)))

    response = client.post("/api/v1/auth/password-reset/request", json={"email": "student@example.com"})
    assert response.status_code == 202
    assert response.json()["message"] == "If an account exists for that address, a reset link will be sent."
    assert sent[0][0] == "student@example.com"
    raw_token = parse_qs(urlparse(sent[0][1]).query)["token"][0]
    assert len(raw_token) >= 32

    changed = client.post("/api/v1/auth/password-reset/complete", json={
        "token": raw_token, "password": "new-safe-password-456",
    })
    assert changed.status_code == 200
    assert client.post("/api/v1/auth/login", json={
        "email": "student@example.com", "password": "safe-test-password-123",
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "student@example.com", "password": "new-safe-password-456",
    }).status_code == 200
    assert client.post("/api/v1/auth/password-reset/complete", json={
        "token": raw_token, "password": "another-safe-password-789",
    }).status_code == 400


def test_password_reset_request_does_not_reveal_unknown_email(client, monkeypatch):
    configure_reset_email(monkeypatch)
    sent = []
    monkeypatch.setattr("backend.app.api.auth.send_password_reset_email",
                        lambda *args: sent.append(args))
    existing = client.post("/api/v1/auth/password-reset/request", json={"email": "student@example.com"})
    missing = client.post("/api/v1/auth/password-reset/request", json={"email": "missing@example.com"})
    assert existing.status_code == missing.status_code == 202
    assert existing.json() == missing.json()
    assert sent == []


def test_password_reset_is_honest_when_smtp_is_not_configured(client):
    assert register(client).status_code == 201
    response = client.post("/api/v1/auth/password-reset/request", json={"email": "student@example.com"})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
