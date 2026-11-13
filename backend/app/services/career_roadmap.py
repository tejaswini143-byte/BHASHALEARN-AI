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
    "mathematics": {"name": "Mathematics for computing", "prerequisites": ["digital-literacy"]},
    "machine-learning": {"name": "Machine learning", "prerequisites": ["python", "statistics", "data-analysis"]},
    "deep-learning": {"name": "Deep learning", "prerequisites": ["machine-learning"]},
    "cloud-basics": {"name": "Cloud fundamentals", "prerequisites": ["digital-literacy", "version-control"]},
    "cybersecurity": {"name": "Cybersecurity fundamentals", "prerequisites": ["digital-literacy", "networking"]},
    "networking": {"name": "Networking fundamentals", "prerequisites": ["digital-literacy"]},
    "linux": {"name": "Linux fundamentals", "prerequisites": ["digital-literacy"]},
    "devops": {"name": "DevOps practices", "prerequisites": ["linux", "cloud-basics", "version-control"]},
    "ui-ux": {"name": "UI and UX design", "prerequisites": ["digital-literacy"]},
    "design-systems": {"name": "Design systems and accessibility", "prerequisites": ["ui-ux", "html-css"]},
    "problem-solving": {"name": "Problem solving", "prerequisites": ["programming-basics"]},
    "version-control": {"name": "Version control", "prerequisites": ["digital-literacy"]},
    "portfolio": {"name": "Portfolio building", "prerequisites": ["communication"]},
    "interview-prep": {"name": "Interview preparation", "prerequisites": ["communication", "problem-solving"]},
}

CAREERS: dict[str, dict[str, object]] = {
    "software-developer": {"title": "Software developer", "skills": ["digital-literacy", "programming-basics", "python", "problem-solving", "version-control", "communication", "portfolio", "interview-prep"]},
    "web-developer": {"title": "Web developer", "skills": ["digital-literacy", "web-basics", "html-css", "javascript", "version-control", "communication", "portfolio", "interview-prep"]},
    "data-analyst": {"title": "Data analyst", "skills": ["digital-literacy", "programming-basics", "python", "statistics", "data-analysis", "communication", "portfolio", "interview-prep"]},
    "ai-engineer": {"title": "AI engineer", "skills": ["digital-literacy", "programming-basics", "python", "mathematics", "statistics", "data-analysis", "machine-learning", "deep-learning", "version-control", "communication", "portfolio", "interview-prep"]},
    "machine-learning-engineer": {"title": "Machine learning engineer", "skills": ["digital-literacy", "programming-basics", "python", "mathematics", "statistics", "data-analysis", "machine-learning", "deep-learning", "version-control", "cloud-basics", "portfolio"]},
    "data-scientist": {"title": "Data scientist", "skills": ["digital-literacy", "programming-basics", "python", "mathematics", "statistics", "data-analysis", "machine-learning", "communication", "portfolio"]},
    "full-stack-developer": {"title": "Full-stack developer", "skills": ["digital-literacy", "programming-basics", "web-basics", "html-css", "javascript", "version-control", "problem-solving", "communication", "portfolio"]},
    "cybersecurity-analyst": {"title": "Cybersecurity analyst", "skills": ["digital-literacy", "networking", "linux", "cybersecurity", "python", "communication", "portfolio"]},
    "cloud-engineer": {"title": "Cloud engineer", "skills": ["digital-literacy", "linux", "networking", "version-control", "cloud-basics", "devops", "python", "portfolio"]},
    "devops-engineer": {"title": "DevOps engineer", "skills": ["digital-literacy", "linux", "networking", "version-control", "cloud-basics", "devops", "python", "portfolio"]},
    "ui-ux-designer": {"title": "UI/UX designer", "skills": ["digital-literacy", "ui-ux", "design-systems", "communication", "portfolio", "interview-prep"]},
    "custom": {"title": "Custom learning goal", "skills": ["digital-literacy", "communication", "portfolio"]},
}

CAREER_TELUGU = {
    "software-developer": "సాఫ్ట్‌వేర్ డెవలపర్", "web-developer": "వెబ్ డెవలపర్",
    "data-analyst": "డేటా విశ్లేషకుడు", "ai-engineer": "ఏఐ ఇంజనీర్",
    "machine-learning-engineer": "మెషిన్ లెర్నింగ్ ఇంజనీర్", "data-scientist": "డేటా శాస్త్రవేత్త",
    "full-stack-developer": "ఫుల్-స్టాక్ డెవలపర్", "cybersecurity-analyst": "సైబర్ భద్రత విశ్లేషకుడు",
    "cloud-engineer": "క్లౌడ్ ఇంజనీర్", "devops-engineer": "డెవ్‌ఆప్స్ ఇంజనీర్",
    "ui-ux-designer": "యూఐ/యూఎక్స్ డిజైనర్", "custom": "అనుకూల అభ్యాస లక్ష్యం",
}

SKILL_TELUGU = {
    "digital-literacy": "డిజిటల్ అక్షరాస్యత", "programming-basics": "ప్రోగ్రామింగ్ పునాదులు",
    "python": "పైథాన్", "web-basics": "వెబ్ పునాదులు", "html-css": "హెచ్‌టీఎంఎల్ మరియు సిఎస్ఎస్",
    "javascript": "జావాస్క్రిప్ట్", "data-analysis": "డేటా విశ్లేషణ", "statistics": "గణాంకాలు",
    "communication": "సంభాషణ నైపుణ్యాలు", "mathematics": "కంప్యూటింగ్ గణితం",
    "machine-learning": "మెషిన్ లెర్నింగ్", "deep-learning": "డీప్ లెర్నింగ్",
    "cloud-basics": "క్లౌడ్ పునాదులు", "cybersecurity": "సైబర్ భద్రత పునాదులు",
    "networking": "నెట్‌వర్కింగ్ పునాదులు", "linux": "లినక్స్ పునాదులు",
    "devops": "డెవ్‌ఆప్స్ విధానాలు", "ui-ux": "యూఐ మరియు యూఎక్స్ రూపకల్పన",
    "design-systems": "డిజైన్ వ్యవస్థలు మరియు ప్రాప్యత",
    "problem-solving": "సమస్య పరిష్కారం", "version-control": "వెర్షన్ నియంత్రణ",
    "portfolio": "పోర్ట్‌ఫోలియో నిర్మాణం", "interview-prep": "ఇంటర్వ్యూ సిద్ధత",
}
for _skill_key, _skill in SKILLS.items():
    _skill["name_te"] = SKILL_TELUGU.get(_skill_key, _skill["name"])

LEVELS = {"beginner", "intermediate", "advanced"}
LANGUAGES = {"telugu", "english", "mixed"}
OBJECTIVE_ASSESSMENTS = {"programming-basics": "dijkstra shortest path", "problem-solving": "dijkstra shortest path"}

RESOURCES: dict[str, list[dict[str, str | bool | None]]] = {
    "python": [{"title": "Python Tutorial", "url": "https://docs.python.org/3/tutorial/", "kind": "official documentation", "free": True}],
    "web-basics": [{"title": "MDN Learn Web Development", "url": "https://developer.mozilla.org/en-US/docs/Learn_web_development", "kind": "tutorial", "free": True}],
    "html-css": [{"title": "MDN HTML and CSS", "url": "https://developer.mozilla.org/en-US/docs/Learn_web_development/Core", "kind": "official tutorials", "free": True}],
    "javascript": [{"title": "MDN JavaScript Guide", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide", "kind": "official documentation", "free": True}],
    "version-control": [{"title": "Git Book", "url": "https://git-scm.com/book/en/v2", "kind": "official book", "free": True}],
    "data-analysis": [{"title": "pandas Getting Started", "url": "https://pandas.pydata.org/docs/getting_started/index.html", "kind": "official tutorials", "free": True}],
    "machine-learning": [{"title": "scikit-learn User Guide", "url": "https://scikit-learn.org/stable/user_guide.html", "kind": "official documentation", "free": True}],
    "deep-learning": [{"title": "PyTorch Tutorials", "url": "https://pytorch.org/tutorials/", "kind": "official tutorials", "free": True}],
    "cloud-basics": [{"title": "AWS Cloud Practitioner training", "url": "https://aws.amazon.com/training/learn-about/cloud-practitioner/", "kind": "training catalog (access varies by item)", "free": None}],
    "cybersecurity": [{"title": "CISA Cybersecurity Training and Exercises", "url": "https://www.cisa.gov/cybersecurity-training-exercises", "kind": "official resources", "free": True}],
    "networking": [{"title": "Cloudflare: What is the network layer?", "url": "https://www.cloudflare.com/learning/network-layer/what-is-the-network-layer/", "kind": "tutorial", "free": True}],
    "linux": [{"title": "Ubuntu Command Line for Beginners", "url": "https://ubuntu.com/tutorials/command-line-for-beginners", "kind": "official tutorial", "free": True}],
    "ui-ux": [{"title": "Material Design Foundations", "url": "https://m3.material.io/foundations", "kind": "design reference", "free": True}],
    "design-systems": [{"title": "W3C Web Accessibility Initiative", "url": "https://www.w3.org/WAI/fundamentals/", "kind": "official guidance", "free": True}],
}


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
            "title_te": str(SKILLS[key]["name_te"]),
            "position": n, "prerequisite_skills": list(SKILLS[key]["prerequisites"]),
            "course_id": items[0].course_id if items else None,
            "course_title": items[0].course_title if items else None,
            "lesson_id": items[0].lesson_id if items else None,
            "lesson_title": items[0].lesson_title if items else None,
            "practice": f"Complete a small {SKILLS[key]['name'].lower()} practice task.",
            "practice_te": f"{SKILLS[key]['name_te']} అంశంపై ఒక చిన్న సాధన చేయండి.",
            "assessment": f"Check your understanding of {SKILLS[key]['name']}.",
            "assessment_topic": OBJECTIVE_ASSESSMENTS.get(key),
            "milestone_description": f"Complete the {SKILLS[key]['name']} learning and practice steps.",
            "milestone_description_te": f"{SKILLS[key]['name_te']} అభ్యాసం మరియు సాధన దశలను పూర్తి చేయండి.",
            "project": f"Add one {SKILLS[key]['name']} example to a portfolio project.",
            "resources": RESOURCES.get(key, []),
            "estimated_hours": 4 if goal["education_level"] == "beginner" else 3,
            "milestone_id": milestone_id,
            "completed": milestone_id in completed,
        })
    weekly_minutes = goal["weekly_minutes"]
    study_days = max(1, min(7, int(goal.get("study_days_per_week", 5))))
    daily_minutes = max(15, min(480, int(goal.get("daily_minutes", 120))))
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][:study_days]
    schedulable_minutes = min(weekly_minutes, daily_minutes * study_days)
    weekly_plan = [{"day": day, "minutes": schedulable_minutes // study_days + (1 if i < schedulable_minutes % study_days else 0),
                    "activity": "Learn and practise the next roadmap skill."}
                   for i, day in enumerate(day_names)]
    return {"goal_id": goal["id"], "career_key": goal["career_key"],
            "career_title": goal.get("custom_goal") or CAREERS[goal["career_key"]]["title"],
            "career_title_te": CAREER_TELUGU.get(goal["career_key"], "అభ్యాస లక్ష్యం"),
            "summary": f"A general learning path toward {goal.get('custom_goal') or CAREERS[goal['career_key']]['title']}. It is not a real-time employment forecast.",
            "summary_te": f"{goal.get('custom_goal') or CAREER_TELUGU.get(goal['career_key'], CAREERS[goal['career_key']]['title'])} లక్ష్యానికి అవసరమైన నైపుణ్యాలను క్రమంగా నేర్చుకునే సాధారణ మార్గం. ఇది ఉద్యోగాల ప్రత్యక్ష అంచనా కాదు.",
            "language": goal["preferred_language"], "phases": phases, "weekly_plan": weekly_plan,
            "available_minutes_per_day": daily_minutes,
            "scheduled_weekly_minutes": schedulable_minutes,
            "estimated_weeks": max(1, (sum(item["estimated_hours"] for item in phases) * 60 + max(1, schedulable_minutes) - 1) // max(1, schedulable_minutes)),
            "total_estimated_hours": sum(item["estimated_hours"] for item in phases),
            "planner": "deterministic_catalog_fallback"}
