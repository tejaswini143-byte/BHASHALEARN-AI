"""Deterministic career roadmap planning and skill-gap analysis."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass

SKILLS: dict[str, dict[str, object]] = {
    "digital-literacy": {"name": "Digital literacy", "prerequisites": []},
    "programming-basics": {"name": "Programming basics", "prerequisites": ["digital-literacy"]},
    "python": {"name": "Python", "prerequisites": ["programming-basics"]},
    "web-basics": {"name": "Web basics", "prerequisites": ["digital-literacy"]},
    "html-css": {"name": "HTML and CSS", "prerequisites": ["web-basics"]},
    "javascript": {"name": "JavaScript", "prerequisites": ["web-basics", "programming-basics"]},
    "data-analysis": {"name": "Data analysis", "prerequisites": ["python"]},
    "statistics": {"name": "Statistics", "prerequisites": ["digital-literacy"]},
    "communication": {"name": "Communication", "prerequisites": []},
    "problem-solving": {"name": "Problem solving", "prerequisites": ["programming-basics"]},
    "version-control": {"name": "Version control", "prerequisites": ["digital-literacy"]},
    "portfolio": {"name": "Portfolio building", "prerequisites": ["communication"]},
    "interview-prep": {"name": "Interview preparation", "prerequisites": ["communication", "problem-solving"]},
}

CAREERS: dict[str, dict[str, object]] = {
    "software-developer": {"title": "Software developer", "skills": ["digital-literacy", "programming-basics", "python", "problem-solving", "version-control", "communication", "portfolio", "interview-prep"]},
    "web-developer": {"title": "Web developer", "skills": ["digital-literacy", "web-basics", "html-css", "javascript", "version-control", "communication", "portfolio", "interview-prep"]},
    "data-analyst": {"title": "Data analyst", "skills": ["digital-literacy", "programming-basics", "python", "statistics", "data-analysis", "communication", "portfolio", "interview-prep"]},
    "custom": {"title": "Custom learning goal", "skills": ["digital-literacy", "communication", "portfolio"]},
}

LEVELS = {"beginner", "intermediate", "advanced"}
LANGUAGES = {"telugu", "english", "mixed"}
OBJECTIVE_ASSESSMENTS = {"programming-basics": "dijkstra shortest path", "problem-solving": "dijkstra shortest path"}


def topological_skills(required: list[str]) -> list[str]:
    """Sort a goal's dependency closure; reject missing nodes and cycles."""
    closure: set[str] = set()
    visiting: set[str] = set()
    def visit(key: str) -> None:
        if key not in SKILLS:
            raise ValueError(f"Unknown skill: {key}")
        if key in visiting:
            raise ValueError("Skill prerequisites contain a cycle")
        if key in closure:
            return
        visiting.add(key)
        for prerequisite in SKILLS[key]["prerequisites"]:  # type: ignore[union-attr]
            visit(prerequisite)
        visiting.remove(key)
        closure.add(key)
    for item in required:
        visit(item)
    dependencies: dict[str, set[str]] = {key: set(SKILLS[key]["prerequisites"]) & closure for key in closure}  # type: ignore[arg-type]
    ready = deque(sorted(key for key, deps in dependencies.items() if not deps))
    result: list[str] = []
    while ready:
        key = ready.popleft()
        result.append(key)
        for other in sorted(dependencies):
            dependencies[other].discard(key)
            if not dependencies[other] and other not in result and other not in ready:
                ready.append(other)
    if len(result) != len(closure):
        raise ValueError("Skill prerequisites contain a cycle")
    return result


def skill_gaps(required: list[str], profiles: list[dict], demonstrated: set[str]) -> list[dict]:
    reported = {item["skill_key"]: item for item in profiles}
    ordered = topological_skills(required)
    rows = []
    for index, key in enumerate(ordered):
        level = reported.get(key, {}).get("proficiency")
        if key in demonstrated:
            state = "already_demonstrated"
        elif level and level != "unknown":
            state = "self_reported"
        elif level == "unknown":
            state = "needs_assessment"
        elif index == 0 or all(p in demonstrated for p in SKILLS[key]["prerequisites"]):
            state = "recommended_next" if not reported.get(key, {}).get("assessed") else "needs_assessment"
        else:
            state = "not_started"
        rows.append({"skill_key": key, "name": SKILLS[key]["name"], "status": state,
                     "self_assessed_proficiency": level, "verified": key in demonstrated,
                     "prerequisites": list(SKILLS[key]["prerequisites"])})
    return rows


@dataclass(frozen=True)
class CatalogItem:
    course_id: str
    course_title: str
    lesson_id: str | None
    lesson_title: str | None
    skill_key: str


def build_plan(goal: dict, skill_rows: list[dict], catalog: list[CatalogItem], previous: dict | None = None) -> dict:
    """Build a validated roadmap using only real catalog IDs."""
    required = list(CAREERS[goal["career_key"]]["skills"])
    order = topological_skills(required)
    by_skill: dict[str, list[CatalogItem]] = defaultdict(list)
    for item in catalog:
        by_skill[item.skill_key].append(item)
    completed = set((previous or {}).get("completed_milestones", []))
    rows_by_skill = {row["skill_key"]: row for row in skill_rows}
    phases = []
    for n, key in enumerate(order, 1):
        status = rows_by_skill[key]["status"]
        milestone_id = f"{goal['career_key']}-{key}-complete"
        if status == "already_demonstrated" and milestone_id not in completed:
            continue
        items = by_skill.get(key, [])
        phases.append({
            "id": f"{goal['career_key']}-{key}", "skill_key": key, "title": SKILLS[key]["name"],
            "title_te": f"{SKILLS[key]['name']} ???????????",
            "position": n, "prerequisite_skills": list(SKILLS[key]["prerequisites"]),
            "course_id": items[0].course_id if items else None,
            "course_title": items[0].course_title if items else None,
            "lesson_id": items[0].lesson_id if items else None,
            "lesson_title": items[0].lesson_title if items else None,
            "practice": f"Complete a small {SKILLS[key]['name'].lower()} practice task.",
            "practice_te": f"{SKILLS[key]['name']} ?? ????? ??????? ?????? ??????.",
            "assessment": f"Check your understanding of {SKILLS[key]['name']}.",
            "assessment_topic": OBJECTIVE_ASSESSMENTS.get(key),
            "milestone_description": f"Complete the {SKILLS[key]['name']} learning and practice steps.",
            "milestone_description_te": f"{SKILLS[key]['name']} ??????? ????? ???? ????? ?????? ??????.",
            "project": f"Add one {SKILLS[key]['name']} example to a portfolio project.",
            "estimated_hours": 4 if goal["education_level"] == "beginner" else 3,
            "milestone_id": milestone_id,
            "completed": milestone_id in completed,
        })
    weekly_minutes = goal["weekly_minutes"]
    weekly_plan = [{"day": day, "minutes": weekly_minutes // 5 + (1 if i < weekly_minutes % 5 else 0),
                    "activity": "Learn and practise the next roadmap skill."}
                   for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
    return {"goal_id": goal["id"], "career_key": goal["career_key"],
            "career_title": goal.get("custom_goal") or CAREERS[goal["career_key"]]["title"],
            "summary": f"A general learning path toward {goal.get('custom_goal') or CAREERS[goal['career_key']]['title']}. It is not a real-time employment forecast.",
            "summary_te": f"{goal.get('custom_goal') or CAREERS[goal['career_key']]['title']} ???? ?????? ?????? ??????. ??? ???????? ???????? ????? ????.",
            "language": goal["preferred_language"], "phases": phases, "weekly_plan": weekly_plan,
            "total_estimated_hours": sum(item["estimated_hours"] for item in phases),
            "planner": "deterministic_catalog_fallback"}
