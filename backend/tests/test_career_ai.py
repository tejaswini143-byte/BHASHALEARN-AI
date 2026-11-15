"""Schema and data-boundary tests for mocked Future Seeker Gemini guidance."""
import json

import pytest
from fastapi import HTTPException

from backend.app.services import career_ai


def _valid(skill_keys):
    return json.dumps({
        "summary_en": "Start with prerequisites and practise one concept at a time.",
        "summary_te": "ముందుగా పునాదులను నేర్చుకుని ప్రతి అంశాన్ని సాధన చేయండి.",
        "advice": [{
            "skill_key": key, "priority": 1, "estimated_hours": 8,
            "explanation_en": f"Build confidence with {key} before advancing.",
            "explanation_te": f"{key} నైపుణ్యాన్ని సాధనతో అభివృద్ధి చేయండి.",
            "next_step_en": f"Practise a small {key} exercise.",
            "next_step_te": f"{key} పై చిన్న సాధన చేయండి.",
        } for key in skill_keys]}, ensure_ascii=False)


def test_gemini_guidance_requires_exact_validated_skill_set(monkeypatch):
    monkeypatch.setattr(career_ai, "generate_tutor_reply", lambda *_: _valid(["python", "statistics"]))
    result = career_ai.analyze_skill_gaps(
        goal={"career_title": "Data scientist", "weekly_minutes": 300},
        profile=[{"skill_key": "python", "proficiency": "beginner"}],
        gaps=[{"skill_key": key, "status": "self_reported", "self_assessed_proficiency": "beginner",
               "prerequisites": []} for key in ["python", "statistics"]],
    )
    assert result["provider"] == "gemini"
    assert {item["skill_key"] for item in result["advice"]} == {"python", "statistics"}
    assert result["disclaimer"]


@pytest.mark.parametrize("keys", [["python", "python"], ["python", "unknown-skill"], ["python"]])
def test_gemini_guidance_rejects_duplicate_unknown_or_missing_skills(monkeypatch, keys):
    monkeypatch.setattr(career_ai, "generate_tutor_reply", lambda *_: _valid(keys))
    with pytest.raises(HTTPException) as error:
        career_ai.analyze_skill_gaps(
            goal={"career_title": "Data scientist", "weekly_minutes": 300}, profile=[],
            gaps=[{"skill_key": key, "status": "not_started", "self_assessed_proficiency": None,
                   "prerequisites": []} for key in ["python", "statistics"]],
        )
    assert error.value.status_code == 502


def test_gemini_payload_contains_learning_profile_but_no_provider_secrets(monkeypatch):
    captured = {}
    def mock_provider(instruction, history):
        captured["instruction"] = instruction
        captured["payload"] = json.loads(history[0]["content"])
        return _valid(["python"])
    monkeypatch.setattr(career_ai, "generate_tutor_reply", mock_provider)
    career_ai.analyze_skill_gaps(
        goal={"career_title": "Software developer", "field_of_study": "Computing",
              "weekly_minutes": 300, "learning_format": "practice", "constraints": ["phone only"]},
        profile=[], gaps=[{"skill_key": "python", "status": "not_started",
                           "self_assessed_proficiency": None, "prerequisites": []}],
    )
    assert captured["payload"]["field_of_study"] == "Computing"
    assert captured["payload"]["constraints"] == ["phone only"]
    assert "api_key" not in captured["payload"]
    assert "employment" in captured["instruction"].lower()


def test_career_mentor_uses_only_current_roadmap_context_and_bounds_reply(monkeypatch):
    captured = {}

    def mock_provider(instruction, history):
        captured["instruction"] = instruction
        captured["payload"] = json.loads(history[0]["content"])
        return "Try a small Python project first."

    monkeypatch.setattr(career_ai, "generate_tutor_reply", mock_provider)
    result = career_ai.mentor_reply(
        goal={"career_title": "AI Engineer", "education_level": "beginner", "weekly_minutes": 300},
        profile=[{"skill_key": "python", "proficiency": "beginner"}],
        roadmap={"version_number": 2, "phases": [{"title": "Python", "skill_key": "python",
                   "completed": False, "prerequisite_skills": []}], "progress": {"completed_milestones": 0}},
        question="What should I learn next?", language="telugu")
    context = captured["payload"]["future_seeker_context"]
    assert context["career_goal"] == "AI Engineer"
    assert context["roadmap_version"] == 2
    assert context["skills"] == [{"skill_key": "python", "proficiency": "beginner"}]
    assert captured["payload"]["question"] == "What should I learn next?"
    assert "natural Telugu" in captured["instruction"]
    assert result["provider"] == "gemini" and result["roadmap_version"] == 2
    monkeypatch.setattr(career_ai, "generate_tutor_reply", lambda *_: " ")
    with pytest.raises(HTTPException) as error:
        career_ai.mentor_reply(goal={}, profile=[], roadmap={}, question="Help", language="english")
    assert error.value.status_code == 502
