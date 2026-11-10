"""Authenticated, student-owned career goals, skill profiles, and roadmaps."""
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import CareerGoal, CareerLessonCompletion, CareerMilestoneCompletion, CareerStudyWeek, Course, Lesson, LearningProgress, Student, StudentSkillProfile
from backend.app.db.session import get_db
from backend.app.services.career_roadmap import CAREERS, LANGUAGES, LEVELS, SKILLS, CatalogItem, build_plan, skill_gaps

router = APIRouter(prefix="/career", tags=["career roadmap"])


class GoalCreate(BaseModel):
    career_key: str = Field(min_length=1, max_length=64)
    education_level: str = Field(min_length=1, max_length=32)
    interests: list[str] = Field(default_factory=list, max_length=12)
    weekly_minutes: int = Field(ge=30, le=2400)
    preferred_language: str = "mixed"
    target_date: date | None = None
    custom_goal: str | None = Field(default=None, max_length=160)

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip()[:80] for value in values if value.strip()))
        return cleaned

    @field_validator("career_key")
    @classmethod
    def valid_career(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CAREERS:
            raise ValueError("Choose one of the supported career directions")
        return value

    @field_validator("education_level")
    @classmethod
    def valid_level(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in LEVELS:
            raise ValueError("Education level must be beginner, intermediate, or advanced")
        return value

    @field_validator("preferred_language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in LANGUAGES:
            raise ValueError("Language must be English, Telugu, or mixed")
        return value

    @model_validator(mode="after")
    def require_custom_goal(self):
        if self.career_key == "custom" and not (self.custom_goal and self.custom_goal.strip()):
            raise ValueError("Describe your custom learning goal")
        if self.custom_goal is not None:
            self.custom_goal = self.custom_goal.strip()[:160] or None
        return self


class SkillInput(BaseModel):
    skill_key: str
    proficiency: str

    @field_validator("skill_key")
    @classmethod
    def known_skill(cls, value: str) -> str:
        if value not in SKILLS:
            raise ValueError("Unknown skill")
        return value

    @field_validator("proficiency")
    @classmethod
    def valid_proficiency(cls, value: str) -> str:
        if value not in {"unknown", "beginner", "intermediate", "advanced"}:
            raise ValueError("Proficiency must be unknown, beginner, intermediate, or advanced")
        return value


class StudyWeekUpdate(BaseModel):
    week_start: date
    studied_minutes: int = Field(ge=0, le=2400)

    @field_validator("week_start")
    @classmethod
    def monday_only(cls, value: date) -> date:
        if value.weekday() != 0:
            raise ValueError("week_start must be a Monday")
        if value > date.today():
            raise ValueError("week_start cannot be in the future")
        return value

def _owned_goal(goal_id: str, student: Student, db: Session) -> CareerGoal:
    goal = db.scalar(select(CareerGoal).where(CareerGoal.id == goal_id, CareerGoal.student_id == student.id))
    if goal is None:
        raise HTTPException(status_code=404, detail="Career goal not found")
    return goal


def _goal_json(goal: CareerGoal) -> dict:
    return {"id": goal.id, "career_key": goal.career_key, "career_title": goal.custom_goal or CAREERS[goal.career_key]["title"],
            "custom_goal": goal.custom_goal,
            "education_level": goal.education_level, "interests": json.loads(goal.interests_json),
            "weekly_minutes": goal.weekly_minutes, "preferred_language": goal.preferred_language,
            "target_date": goal.target_date, "active": goal.active}


def _profile(student_id: str, db: Session) -> list[dict]:
    return [{"skill_key": row.skill_key, "proficiency": row.proficiency} for row in db.scalars(
        select(StudentSkillProfile).where(StudentSkillProfile.student_id == student_id)
    ).all()]


def _demonstrated(student_id: str, db: Session) -> set[str]:
    # Only objective, recorded assessment evidence can mark a skill demonstrated.
    progress = db.scalars(select(LearningProgress).where(
        LearningProgress.student_id == student_id,
        LearningProgress.evidence_attempts >= 3,
        LearningProgress.mastery_score >= 80,
    )).all()
    evidence = {"python": ("python",), "programming-basics": ("programming", "dijkstra"),
                "problem-solving": ("dijkstra",),
                "web-basics": ("web",), "data-analysis": ("data analysis", "statistics"),
                "statistics": ("statistics",), "communication": ("communication",)}
    topics = [row.topic.lower() for row in progress]
    return {skill for skill, terms in evidence.items() if any(any(term in topic for term in terms) for topic in topics)}


def _catalog(db: Session) -> list[CatalogItem]:
    items: list[CatalogItem] = []
    courses = db.scalars(select(Course).order_by(Course.title, Course.id)).all()
    for course in courses:
        lessons = db.scalars(select(Lesson).where(Lesson.course_id == course.id).order_by(Lesson.position)).all()
        candidates = [(course.title + " " + lesson.title, lesson.id, lesson.title) for lesson in lessons]
        if not candidates:
            candidates = [(course.title, None, None)]
        for text, lesson_id, lesson_title in candidates:
            lowered = text.lower()
            for key, skill in SKILLS.items():
                terms = [key.replace("-", " "), str(skill["name"]).lower()]
                if any(term in lowered for term in terms):
                    items.append(CatalogItem(course.id, course.title, lesson_id, lesson_title, key))
    return items


def _build(goal: CareerGoal, student_id: str, db: Session) -> dict:
    goal_data = _goal_json(goal)
    required = list(CAREERS[goal.career_key]["skills"])
    profile = _profile(student_id, db)
    demonstrated = _demonstrated(student_id, db)
    gaps = skill_gaps(required, profile, demonstrated)
    completions = db.scalars(select(CareerMilestoneCompletion).where(
        CareerMilestoneCompletion.goal_id == goal.id, CareerMilestoneCompletion.student_id == student_id
    )).all()
    done = {row.milestone_id for row in completions}
    plan = build_plan(goal_data, gaps, _catalog(db), {"completed_milestones": list(done)})
    for phase in plan["phases"]:
        phase["completed"] = phase["milestone_id"] in done
    lesson_completions = db.scalars(select(CareerLessonCompletion).where(
        CareerLessonCompletion.goal_id == goal.id, CareerLessonCompletion.student_id == student_id
    )).all()
    completed_lessons = {row.lesson_id for row in lesson_completions}
    for phase in plan["phases"]:
        phase["lesson_completed"] = phase["lesson_id"] in completed_lessons if phase["lesson_id"] else False
    today = date.today()
    current_week = today - timedelta(days=today.weekday())
    previous_week = current_week - timedelta(days=7)
    current_log = db.scalar(select(CareerStudyWeek).where(
        CareerStudyWeek.student_id == student_id, CareerStudyWeek.goal_id == goal.id,
        CareerStudyWeek.week_start == current_week.isoformat(),
    ))
    previous_log = db.scalar(select(CareerStudyWeek).where(
        CareerStudyWeek.student_id == student_id, CareerStudyWeek.goal_id == goal.id,
        CareerStudyWeek.week_start == previous_week.isoformat(),
    ))
    missed = bool(previous_log and previous_log.studied_minutes < previous_log.target_minutes)
    adjusted_minutes = (min(goal.weekly_minutes, max(30, previous_log.studied_minutes))
                        if missed and previous_log else goal.weekly_minutes)
    plan["weekly_plan"] = [{"day": day, "minutes": adjusted_minutes // 5 + (1 if i < adjusted_minutes % 5 else 0),
                            "activity": "Use a shorter focused block and review the last unfinished skill." if missed
                            else "Learn and practise the next roadmap skill."}
                           for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
    plan["skill_gaps"] = gaps
    plan["progress"] = {"completed_milestones": len(done), "total_milestones": len(plan["phases"]),
                        "completed_lessons": len(completed_lessons)}
    plan["study_adjustment"] = {
        "state": "missed_last_week" if missed else "on_track" if previous_log else "not_recorded",
        "previous_target_minutes": previous_log.target_minutes if previous_log else None,
        "previous_studied_minutes": previous_log.studied_minutes if previous_log else None,
        "recommended_weekly_minutes": adjusted_minutes,
        "current_week_start": current_week.isoformat(),
        "current_week_studied_minutes": current_log.studied_minutes if current_log else 0,
    }
    return plan


@router.get("/directions")
def directions(student: Student = Depends(current_student)):
    return {"directions": [{"career_key": key, "title": value["title"], "required_skills": value["skills"]}
                            for key, value in CAREERS.items()],
            "note": "General learning directions; not a real-time employment forecast."}


@router.get("/goals")
def list_goals(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goals = db.scalars(select(CareerGoal).where(CareerGoal.student_id == student.id).order_by(CareerGoal.created_at.desc())).all()
    return [_goal_json(goal) for goal in goals]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = CareerGoal(student_id=student.id, career_key=payload.career_key, custom_goal=payload.custom_goal, education_level=payload.education_level,
                      interests_json=json.dumps(payload.interests, ensure_ascii=False), weekly_minutes=payload.weekly_minutes,
                      preferred_language=payload.preferred_language,
                      target_date=payload.target_date.isoformat() if payload.target_date else None)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_json(goal)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, payload: GoalCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    for key, value in payload.model_dump().items():
        setattr(goal, "interests_json" if key == "interests" else key,
                json.dumps(value, ensure_ascii=False) if key == "interests" else value.isoformat() if key == "target_date" and value else value)
    goal.roadmap_json = None
    db.commit()
    return _goal_json(goal)


@router.get("/skills")
def get_skills(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    profiles = _profile(student.id, db)
    return {"skills": SKILLS, "profile": profiles}


@router.put("/skills")
def update_skills(payload: list[SkillInput], student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if len(payload) > len(SKILLS) or len({item.skill_key for item in payload}) != len(payload):
        raise HTTPException(status_code=422, detail="Skills must be unique and within the supported taxonomy")
    for item in payload:
        profile = db.scalar(select(StudentSkillProfile).where(StudentSkillProfile.student_id == student.id,
                                                               StudentSkillProfile.skill_key == item.skill_key))
        if profile is None:
            db.add(StudentSkillProfile(student_id=student.id, skill_key=item.skill_key, proficiency=item.proficiency))
        else:
            profile.proficiency = item.proficiency
    db.commit()
    return {"profile": _profile(student.id, db), "evidence_type": "self_reported_only"}


@router.post("/goals/{goal_id}/roadmap")
def generate_roadmap(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    result = _build(goal, student.id, db)
    goal.roadmap_json = json.dumps(result, ensure_ascii=False)
    db.commit()
    return result


@router.get("/goals/{goal_id}/roadmap")
def get_roadmap(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    if not goal.roadmap_json:
        return _build(goal, student.id, db)
    result = json.loads(goal.roadmap_json)
    done = {row.milestone_id for row in db.scalars(select(CareerMilestoneCompletion).where(
        CareerMilestoneCompletion.goal_id == goal.id, CareerMilestoneCompletion.student_id == student.id)).all()}
    for phase in result["phases"]:
        phase["completed"] = phase["milestone_id"] in done
    lesson_done = {row.lesson_id for row in db.scalars(select(CareerLessonCompletion).where(
        CareerLessonCompletion.goal_id == goal.id, CareerLessonCompletion.student_id == student.id)).all()}
    for phase in result["phases"]:
        phase["lesson_completed"] = phase["lesson_id"] in lesson_done if phase["lesson_id"] else False
    result["progress"] = {"completed_milestones": len(done), "total_milestones": len(result["phases"]),
                          "completed_lessons": len(lesson_done)}
    return result


@router.post("/goals/{goal_id}/replan")
def replan(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    result = _build(goal, student.id, db)
    goal.roadmap_json = json.dumps(result, ensure_ascii=False)
    db.commit()
    return result


@router.put("/goals/{goal_id}/weekly-progress")
def update_weekly_progress(goal_id: str, payload: StudyWeekUpdate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    week_start = payload.week_start.isoformat()
    entry = db.scalar(select(CareerStudyWeek).where(
        CareerStudyWeek.student_id == student.id, CareerStudyWeek.goal_id == goal.id,
        CareerStudyWeek.week_start == week_start,
    ))
    if entry is None:
        entry = CareerStudyWeek(student_id=student.id, goal_id=goal.id, week_start=week_start,
                                target_minutes=goal.weekly_minutes, studied_minutes=payload.studied_minutes)
        db.add(entry)
    else:
        entry.target_minutes = goal.weekly_minutes
        entry.studied_minutes = payload.studied_minutes
    db.commit()
    return {"week_start": week_start, "target_minutes": goal.weekly_minutes,
            "studied_minutes": payload.studied_minutes,
            "status": "on_track" if payload.studied_minutes >= goal.weekly_minutes else "below_target"}


@router.post("/goals/{goal_id}/lessons/{lesson_id}/complete")
def complete_lesson(goal_id: str, lesson_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    plan = json.loads(goal.roadmap_json) if goal.roadmap_json else _build(goal, student.id, db)
    phase = next((item for item in plan["phases"] if item["lesson_id"] == lesson_id and item["course_id"]), None)
    if phase is None:
        raise HTTPException(status_code=404, detail="Recommended lesson not found")
    if db.get(Lesson, lesson_id) is None or db.get(Course, phase["course_id"]) is None:
        raise HTTPException(status_code=404, detail="Catalog lesson not found")
    db.add(CareerLessonCompletion(student_id=student.id, goal_id=goal.id,
                                  course_id=phase["course_id"], lesson_id=lesson_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return get_roadmap(goal_id, student, db)


@router.post("/goals/{goal_id}/milestones/{milestone_id}/complete")
def complete_milestone(goal_id: str, milestone_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    roadmap = json.loads(goal.roadmap_json) if goal.roadmap_json else _build(goal, student.id, db)
    if not any(phase["milestone_id"] == milestone_id for phase in roadmap["phases"]):
        raise HTTPException(status_code=404, detail="Milestone not found")
    entry = CareerMilestoneCompletion(student_id=student.id, goal_id=goal.id, milestone_id=milestone_id)
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # repeat completion is an idempotent success
    return get_roadmap(goal_id, student, db)


@router.get("/recommendations")
def recommendations(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = db.scalar(select(CareerGoal).where(CareerGoal.student_id == student.id, CareerGoal.active.is_(True))
                      .order_by(CareerGoal.updated_at.desc()))
    if not goal:
        return {"recommendations": [], "next_action": "Choose a career direction to begin."}
    roadmap = get_roadmap(goal.id, student, db)
    next_phase = next((phase for phase in roadmap["phases"] if not phase["completed"]), None)
    return {"recommendations": ([{"kind": "skill", "skill_key": next_phase["skill_key"],
                                    "action": f"Start {next_phase['title']}."}] if next_phase else []),
            "next_action": next_phase["practice"] if next_phase else "Choose another learning direction when ready."}
