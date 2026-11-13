"""Feature 4 Phase 3 catalog and schema regression checks."""
import pytest
from pydantic import ValidationError

from backend.app.api.visual_lessons import CATALOG, LessonEnvelope


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
    settings = Settings(api_prefix="/api/v1", local_scheduler_enabled=False)
    with TestClient(create_app(settings)) as client:
        assert client.get(f"{settings.api_prefix}/visual-lessons").status_code in {401, 403}
        assert client.get(f"{settings.api_prefix}/visual-lessons/geometry").status_code in {401, 403}
