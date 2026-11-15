"""Feature 4 Phase 3 catalog and schema regression checks."""
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.api.visual_lessons import CATALOG, GeneratedLessonEnvelope, LessonEnvelope, LessonStateUpdate
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db


@pytest.fixture
def visual_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import create_app

    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "visual-lessons-test-secret-key-with-32-characters")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'visual-lessons.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.state.test_engine = engine
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def _login_visual(client, email):
    password = "visual-test-password-123"
    registered = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Visual Learner", "password": password})
    assert registered.status_code == 201, registered.text
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert logged_in.status_code == 200
    return {"Authorization": "Bearer " + logged_in.json()["access_token"]}


def _create_visual_session(client, headers):
    created = client.post("/api/v1/sessions", headers=headers, json={"topic": "Visual lesson", "language": "english"})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def test_catalog_is_bilingual_and_versioned():
    assert set(CATALOG) == {"solar-system", "geometry", "pendulum"}
    for key, item in CATALOG.items():
        assert item.version == 1
        assert item.scene == {"kind": key}
        assert item.lesson.id == key
        assert item.lesson.title.en.strip()
        assert item.lesson.title.te.strip()
        assert all(step.explanation.en and step.explanation.te for step in item.lesson.steps)


def test_rejects_mismatched_scene():
    original = CATALOG["geometry"].model_dump()
    original["scene"] = {"kind": "pendulum"}
    with pytest.raises(ValidationError, match="Scene kind must match"):
        LessonEnvelope.model_validate(original)


def test_rejects_unknown_fields_and_missing_telugu():
    original = CATALOG["geometry"].model_dump()
    original["lesson"]["title"]["te"] = ""
    with pytest.raises(ValidationError):
        LessonEnvelope.model_validate(original)
    original = CATALOG["geometry"].model_dump()
    original["lesson"]["steps"][0]["unexpected_command"] = "execute"
    with pytest.raises(ValidationError):
        LessonEnvelope.model_validate(original)


def test_routes_require_authentication():
    from fastapi.testclient import TestClient
    from backend.app.main import create_app
    from backend.app.config import Settings
    from backend.app.db.session import get_db

    settings = Settings(api_prefix="/api/v1", local_scheduler_enabled=False)
    app = create_app(settings)

    def no_database_needed():
        # An anonymous request must fail before any database query.
        yield None

    app.dependency_overrides[get_db] = no_database_needed
    try:
        with TestClient(app) as client:
            for path in ("/visual-lessons", "/visual-lessons/geometry"):
                response = client.get(f"{settings.api_prefix}{path}")
                assert response.status_code == 401
                assert response.json()["detail"] == "Missing bearer token"
            response = client.get(f"{settings.api_prefix}/visual-lessons/session-state?session_id=00000000-0000-0000-0000-000000000000")
            assert response.status_code == 401
            response = client.post(f"{settings.api_prefix}/visual-lessons/generate", json={"topic": "gravity", "scene_kind": "pendulum", "session_id": "00000000-0000-0000-0000-000000000000"})
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_generated_v2_lesson_accepts_safe_scene_and_rejects_unsupported_parameters():
    lesson = CATALOG["geometry"].lesson.model_dump()
    lesson.update({
        "questions": [{"prompt": {"en": "Which shape?", "te": "ఏ ఆకారం?"}, "answer": {"en": "Cube", "te": "ఘనం"}, "explanation": {"en": "Six faces", "te": "ఆరు ముఖాలు"}}],
        "activities": [{"instruction": {"en": "Rotate it", "te": "తిప్పండి"}, "control": "rotate-shape"}],
        "completion_criteria": [{"en": "Name the faces", "te": "ముఖాలను చెప్పండి"}],
    })
    for step in lesson["steps"]:
        step["scene_id"] = "geometry"
    valid = {"version": 2, "lesson": lesson, "scene": {"kind": "geometry", "parameters": {"shape": "cube", "size": 1.2}}}
    assert GeneratedLessonEnvelope.model_validate(valid).scene.parameters["shape"] == "cube"
    invalid = {**valid, "scene": {"kind": "geometry", "parameters": {"shape": "cube", "size": 1.2, "script": "alert(1)"}}}
    with pytest.raises(ValidationError, match="Geometry parameters"):
        GeneratedLessonEnvelope.model_validate(invalid)
    invalid = {**valid, "scene": {"kind": "solar-system", "parameters": {"time_scale": 30}}}
    with pytest.raises(ValidationError, match="Scene kind must match"):
        GeneratedLessonEnvelope.model_validate(invalid)


def test_visual_lesson_session_payload_rejects_unapproved_interaction_keys():
    lesson = CATALOG["pendulum"].model_dump()
    valid = LessonStateUpdate.model_validate({
        "session_id": "00000000-0000-0000-0000-000000000000",
        "envelope": lesson,
        "current_step": 0,
        "paused": True,
        "completed": False,
        "interactions": {"length": 1.5, "gravity": 9.81},
        "quiz_responses": ["gravity changes the period"],
    })
    assert valid.interactions["length"] == 1.5
    with pytest.raises(ValidationError, match="Unsupported visual interaction field"):
        LessonStateUpdate.model_validate({
            "session_id": "00000000-0000-0000-0000-000000000000",
            "envelope": lesson,
            "current_step": 0,
            "paused": True,
            "completed": False,
            "interactions": {"javascript": "alert(1)"},
        })


def test_visual_lesson_progress_is_student_owned_and_resumable(visual_client):
    headers = _login_visual(visual_client, "visual-owner@example.com")
    other = _login_visual(visual_client, "visual-other@example.com")
    session_id = _create_visual_session(visual_client, headers)
    payload = {
        "session_id": session_id,
        "envelope": CATALOG["pendulum"].model_dump(mode="json"),
        "current_step": 1,
        "paused": True,
        "completed": True,
        "interactions": {"length": 1.5, "gravity": 9.81},
        "quiz_responses": ["longer pendulum"],
    }
    saved = visual_client.put("/api/v1/visual-lessons/session-state", headers=headers, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["state"]["completed"] is True
    assert saved.json()["state"]["current_step"] == 1
    resumed = visual_client.get(f"/api/v1/visual-lessons/session-state?session_id={session_id}", headers=headers)
    assert resumed.status_code == 200
    assert resumed.json()["state"]["interactions"] == payload["interactions"]
    assert resumed.json()["state"]["quiz_responses"] == payload["quiz_responses"]
    assert visual_client.get(f"/api/v1/visual-lessons/session-state?session_id={session_id}", headers=other).status_code == 404


def test_generated_lesson_is_saved_for_existing_session(visual_client, monkeypatch):
    from backend.app.api import visual_lessons as api

    lesson = CATALOG["geometry"].lesson.model_dump(mode="json")
    lesson.update({
        "questions": [{"prompt": {"en": "How many faces?", "te": "ఎన్ని ముఖాలు?"}, "answer": {"en": "Six", "te": "ఆరు"}, "explanation": {"en": "A cube has six faces.", "te": "ఘనానికి ఆరు ముఖాలు ఉంటాయి."}}],
        "activities": [{"instruction": {"en": "Rotate the cube.", "te": "ఘనాన్ని తిప్పండి."}, "control": "rotate-shape"}],
        "completion_criteria": [{"en": "Describe its faces.", "te": "ముఖాలను వివరించండి."}],
    })
    for step in lesson["steps"]:
        step["scene_id"] = "geometry"
    generated = GeneratedLessonEnvelope.model_validate({
        "version": 2,
        "lesson": lesson,
        "scene": {"kind": "geometry", "parameters": {"shape": "cube", "size": 1.5}},
    })
    monkeypatch.setattr(api, "generate_lesson_with_gemini", lambda _request: generated)
    headers = _login_visual(visual_client, "visual-generation@example.com")
    session_id = _create_visual_session(visual_client, headers)
    created = visual_client.post("/api/v1/visual-lessons/generate", headers=headers, json={
        "topic": "Cube properties", "language": "english", "scene_kind": "geometry", "session_id": session_id,
    })
    assert created.status_code == 200, created.text
    assert created.json()["version"] == 2
    saved = visual_client.get(f"/api/v1/visual-lessons/session-state?session_id={session_id}", headers=headers).json()["state"]
    assert saved["envelope"]["lesson"]["questions"][0]["answer"]["en"] == "Six"
    assert saved["interactions"] == {"shape": "cube", "size": 1.5}
