"""Career planning algorithm contracts with no database dependency."""
import pytest

from backend.app.services.career_roadmap import SKILLS, skill_gaps, topological_skills


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
