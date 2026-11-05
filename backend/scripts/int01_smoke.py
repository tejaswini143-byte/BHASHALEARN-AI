"""INT-01 live FastAPI smoke test. Creates one disposable student and learning session.
Run from repository root: python backend/scripts/int01_smoke.py
Requires running FastAPI, configured PostgreSQL, and applied Alembic migrations.
No API keys or passwords are printed.
"""
import json
import os
import sys
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.environ.get("BHASHALEARN_TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
API = BASE + "/api/v1"


def call(method, path, payload=None, token=None):
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(
        API + path,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read()
        try:
            detail = json.loads(raw)
        except ValueError:
            detail = {"detail": "Non-JSON server error"}
        return exc.code, detail


def check(label, condition, explanation=""):
    if not condition:
        raise AssertionError(label + (": " + explanation if explanation else ""))
    print("PASS:", label)


def main():
    suffix = uuid.uuid4().hex[:12]
    email = "int01-" + suffix + "@example.com"
    password = "TemporaryTest!" + uuid.uuid4().hex[:18]
    print("Testing", BASE, "with a disposable student (database rows will remain).")
    status, health = call("GET", "/health")
    check("API health", status == 200 and health.get("status") == "ok", str(status))
    status, _ = call("GET", "/auth/me")
    check("Protected profile denies anonymous requests", status == 401, str(status))
    status, _ = call("GET", "/sessions")
    check("Protected sessions deny anonymous requests", status == 401, str(status))
    status, student = call("POST", "/auth/register", {
        "email": email, "display_name": "INT01 Test Student", "password": password,
    })
    check("Register student", status == 201 and student.get("email") == email, str(status) + " " + str(student.get("detail") if isinstance(student, dict) else student))
    status, result = call("POST", "/auth/login", {"email": email, "password": password})
    check("Login returns bearer token", status == 200 and bool(result.get("access_token")), str(status))
    token = result["access_token"]
    status, profile = call("GET", "/auth/me", token=token)
    check("Authenticated profile matches registration", status == 200 and profile.get("id") == student["id"], str(status))
    status, prefs = call("GET", "/students/me/preferences", token=token)
    check("Dashboard preferences endpoint", status == 200 and "learning_level" in prefs, str(status))
    status, prefs = call("PUT", "/students/me/preferences", {
        "preferred_language": "mixed", "learning_level": "beginner",
        "learning_goal": "INT-01 API smoke verification",
    }, token)
    check("Update learning preferences", status == 200 and prefs.get("preferred_language") == "mixed", str(status))
    status, prefs = call("GET", "/students/me/preferences", token=token)
    check("Read updated learning preferences", status == 200 and prefs.get("learning_goal") == "INT-01 API smoke verification", str(status))
    status, progress = call("PUT", "/progress", {
        "topic": "INT01 API Smoke Test", "mastery_score": 25, "attempts": 1,
    }, token)
    check("Create learning progress", status == 200 and progress.get("attempts") == 1, str(status))
    status, progress = call("GET", "/progress?limit=100", token=token)
    check("Dashboard progress endpoint", status == 200 and isinstance(progress, list) and any(p.get("topic") == "INT01 API Smoke Test" for p in progress), str(status))
    status, sessions = call("GET", "/sessions?limit=20", token=token)
    check("Dashboard sessions endpoint", status == 200 and isinstance(sessions, list), str(status))
    status, session = call("POST", "/sessions", {"topic": "INT01 API Smoke Test", "language": "mixed"}, token)
    check("Create learning session", status == 201 and session.get("topic") == "INT01 API Smoke Test", str(status))
    session_id = session["id"]
    status, sessions = call("GET", "/sessions?limit=20", token=token)
    check("New session appears in listing", status == 200 and any(s["id"] == session_id for s in sessions), str(status))
    status, message = call("POST", "/sessions/" + session_id + "/messages", {
        "role": "user", "content": "Verify session message persistence",
    }, token)
    check("Create session message", status == 201 and message.get("content") == "Verify session message persistence", str(status))
    status, messages = call("GET", "/sessions/" + session_id + "/messages?limit=500", token=token)
    check("Session message history endpoint", status == 200 and isinstance(messages, list) and any(m.get("content") == "Verify session message persistence" for m in messages), str(status))
    status, _ = call("GET", "/sessions/" + session_id)
    check("Private session denies anonymous requests", status == 401, str(status))
    print("\nINT-01 API smoke checks passed. Browser UI still requires separate verification.")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, URLError, TimeoutError, ValueError, KeyError, AttributeError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)
