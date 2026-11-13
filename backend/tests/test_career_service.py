"""Career planning algorithm contracts with no database dependency."""
import pytest

from backend.app.services.career_roadmap import CAREERS, SKILLS, CatalogItem, build_plan, skill_gaps, topological_skills


def test_skill_gaps_distinguish_evidence_from_self_reported_proficiency():
    rows = skill_gaps(
        ["digital-literacy", "programming-basics", "python"],
        [
            {"skill_key": "programming-basics", "proficiency": "advanced"},
            {"skill_key": "python", "proficiency": "unknown"},
        ],
        {"digital-literacy"},
    )
    assert [row["status"] for row in rows] == ["already_demonstrated", "self_reported", "needs_assessment"]
    assert [row["verified"] for row in rows] == [True, False, False]


def test_dependency_order_includes_prerequisites_once():
    ordered = topological_skills(["javascript", "html-css"])
    assert len(ordered) == len(set(ordered))
    assert ordered.index("web-basics") < ordered.index("html-css")
    assert ordered.index("programming-basics") < ordered.index("javascript")


def test_dependency_cycles_fail_closed(monkeypatch):
    monkeypatch.setitem(SKILLS["digital-literacy"], "prerequisites", ["programming-basics"])
    with pytest.raises(ValueError, match="cycle"):
        topological_skills(["programming-basics"])


def test_future_seeker_catalog_covers_requested_career_directions():
    expected = {"ai-engineer", "machine-learning-engineer", "data-scientist", "software-developer",
                "full-stack-developer", "cybersecurity-analyst", "cloud-engineer", "devops-engineer",
                "data-analyst", "ui-ux-designer"}
    assert expected.issubset(CAREERS)
    for career in expected:
        assert CAREERS[career]["skills"]
        assert all(key in SKILLS for key in CAREERS[career]["skills"])


def test_personalized_plan_respects_daily_capacity_and_uses_verified_catalog_resources():
    goal = {"id": "g", "career_key": "ai-engineer", "education_level": "beginner",
            "weekly_minutes": 240, "daily_minutes": 60, "study_days_per_week": 4,
            "preferred_language": "telugu"}
    gaps = skill_gaps(CAREERS["ai-engineer"]["skills"], [], set())
    plan = build_plan(goal, gaps, [CatalogItem("course", "Python foundations", "lesson", "Python basics", "python")])
    assert [item["day"] for item in plan["weekly_plan"]] == ["Monday", "Tuesday", "Wednesday", "Thursday"]
    assert sum(item["minutes"] for item in plan["weekly_plan"]) == 240
    assert all(item["minutes"] <= 60 for item in plan["weekly_plan"])
    phase = next(item for item in plan["phases"] if item["skill_key"] == "python")
    assert phase["course_id"] == "course" and phase["lesson_id"] == "lesson"
    assert phase["resources"][0]["url"].startswith("https://")
    assert phase["title_te"] != phase["title"]
