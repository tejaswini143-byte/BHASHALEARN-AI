"""Authenticated, student-owned career goals, skill profiles, and roadmaps."""
import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import (CareerGoal, CareerLessonCompletion, CareerMilestoneCompletion,
    CareerRoadmapVersion, CareerSavedResource, CareerStudyWeek, Course, Lesson, LearningAssessmentAttempt,
    LearningProgress, Student, StudentSkillProfile)
from backend.app.db.session import get_db
from backend.app.services.career_roadmap import CAREERS, CAREER_TELUGU, LANGUAGES, LEVELS, SKILLS, CatalogItem, build_plan, skill_gaps
from backend.app.services.career_ai import analyze_skill_gaps

router = APIRouter(prefix="/career", tags=["career roadmap"])


class GoalCreate(BaseModel):
    career_key: str = Field(min_length=1, max_length=64)
    education_level: str = Field(min_length=1, max_length=32)
    field_of_study: str | None = Field(default=None, max_length=120)
    interests: list[str] = Field(default_factory=list, max_length=12)
    weekly_minutes: int = Field(ge=30, le=2400)
    daily_minutes: int = Field(default=120, ge=15, le=480)
    study_days_per_week: int = Field(default=5, ge=1, le=7)
    learning_format: str = "mixed"
    timeframe_weeks: int | None = Field(default=None, ge=1, le=260)
    constraints: list[str] = Field(default_factory=list, max_length=12)
    preferred_language: str = "mixed"
    target_date: date | None = None
    custom_goal: str | None = Field(default=None, max_length=160)
    confirm_major_change: bool = False

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(value.strip()[:80] for value in values if value.strip()))
        return cleaned

    @field_validator("constraints")
    @classmethod
    def clean_constraints(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip()[:160] for value in values if value.strip()))

    @field_validator("field_of_study")
    @classmethod
    def clean_field_of_study(cls, value: str | None) -> str | None:
        return value.strip()[:120] or None if value is not None else None

    @field_validator("learning_format")
    @classmethod
    def valid_learning_format(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"video", "reading", "practice", "mixed"}:
            raise ValueError("Learning format must be video, reading, practice, or mixed")
        return value

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
        if self.weekly_minutes > self.daily_minutes * self.study_days_per_week:
            raise ValueError("Weekly study time must fit the selected daily minutes and study days")
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


class SaveResourceInput(BaseModel):
    resource_url: str = Field(min_length=1, max_length=2048)


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
            "career_title_te": CAREER_TELUGU.get(goal.career_key, "అభ్యాస లక్ష్యం"),
            "custom_goal": goal.custom_goal,
            "education_level": goal.education_level, "field_of_study": goal.field_of_study,
            "interests": json.loads(goal.interests_json), "constraints": json.loads(goal.constraints_json or "[]"),
            "weekly_minutes": goal.weekly_minutes, "daily_minutes": goal.daily_minutes,
            "study_days_per_week": goal.study_days_per_week, "learning_format": goal.learning_format,
            "timeframe_weeks": goal.timeframe_weeks, "preferred_language": goal.preferred_language,
            "target_date": goal.target_date, "active": goal.active}


def _next_version(goal: CareerGoal, db: Session) -> int:
    latest = db.scalars(select(CareerRoadmapVersion).where(
        CareerRoadmapVersion.student_id == goal.student_id,
        CareerRoadmapVersion.goal_id == goal.id,
    )).all()
    return max((row.version_number for row in latest), default=0) + 1


def _archive_current_roadmap(goal: CareerGoal, db: Session, reason: str) -> None:
    if not goal.roadmap_json:
        return
    rows = db.scalars(select(CareerRoadmapVersion).where(
        CareerRoadmapVersion.student_id == goal.student_id,
        CareerRoadmapVersion.goal_id == goal.id,
    )).all()
    if any(row.roadmap_json == goal.roadmap_json for row in rows):
        return
    archived = json.loads(goal.roadmap_json)
    version = _next_version(goal, db)
    archived["version_number"] = version
    db.add(CareerRoadmapVersion(student_id=goal.student_id, goal_id=goal.id,
        version_number=version, roadmap_json=json.dumps(archived, ensure_ascii=False), change_reason=reason))


def _store_new_roadmap(goal: CareerGoal, roadmap: dict, db: Session, reason: str) -> dict:
    version = _next_version(goal, db)
    roadmap["version_number"] = version
    serialized = json.dumps(roadmap, ensure_ascii=False)
    db.add(CareerRoadmapVersion(student_id=goal.student_id, goal_id=goal.id,
        version_number=version, roadmap_json=serialized, change_reason=reason))
    goal.roadmap_json = serialized
    return roadmap


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
    study_days = max(1, min(7, goal.study_days_per_week))
    daily_limit = max(15, min(480, goal.daily_minutes))
    scheduled = min(adjusted_minutes, study_days * daily_limit)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][:study_days]
    plan["weekly_plan"] = [{"day": day, "minutes": scheduled // study_days + (1 if i < scheduled % study_days else 0),
                            "activity": "Use a shorter focused block and review the last unfinished skill." if missed
                            else "Learn and practise the next roadmap skill."}
                           for i, day in enumerate(days)]
    plan["scheduled_weekly_minutes"] = scheduled
    plan["estimated_weeks"] = max(1, (sum(item["estimated_hours"] for item in plan["phases"]) * 60 + max(1, scheduled) - 1) // max(1, scheduled))
    plan["target_timeframe_weeks"] = goal.timeframe_weeks
    plan["timeframe_feasibility"] = ("within_target" if not goal.timeframe_weeks or plan["estimated_weeks"] <= goal.timeframe_weeks else "target_may_be_too_short")
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
    return {"directions": [{"career_key": key, "title": value["title"],
                            "title_te": CAREER_TELUGU.get(key, str(value["title"])),
                            "required_skills": value["skills"]}
                            for key, value in CAREERS.items()],
            "note": "General learning directions; not a real-time employment forecast."}


@router.get("/goals")
def list_goals(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goals = db.scalars(select(CareerGoal).where(CareerGoal.student_id == student.id).order_by(CareerGoal.created_at.desc())).all()
    return [_goal_json(goal) for goal in goals]


@router.post("/goals", status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    db.query(CareerGoal).filter(CareerGoal.student_id == student.id, CareerGoal.active.is_(True)).update({"active": False})
    goal = CareerGoal(student_id=student.id, career_key=payload.career_key, custom_goal=payload.custom_goal, education_level=payload.education_level,
                      field_of_study=payload.field_of_study,
                      interests_json=json.dumps(payload.interests, ensure_ascii=False), weekly_minutes=payload.weekly_minutes,
                      daily_minutes=payload.daily_minutes, study_days_per_week=payload.study_days_per_week,
                      learning_format=payload.learning_format, timeframe_weeks=payload.timeframe_weeks,
                      constraints_json=json.dumps(payload.constraints, ensure_ascii=False),
                      preferred_language=payload.preferred_language,
                      target_date=payload.target_date.isoformat() if payload.target_date else None)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return _goal_json(goal)


@router.put("/goals/{goal_id}")
def update_goal(goal_id: str, payload: GoalCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    major_change = payload.career_key != goal.career_key or payload.custom_goal != goal.custom_goal
    if major_change and not payload.confirm_major_change:
        raise HTTPException(status_code=409, detail="Changing career direction creates a new roadmap version; confirm the change and keep the prior version")
    _archive_current_roadmap(goal, db, "before_goal_update")
    values = payload.model_dump(exclude={"confirm_major_change"})
    values["target_date"] = values["target_date"].isoformat() if values["target_date"] else None
    for key, value in values.items():
        column = {"interests": "interests_json", "constraints": "constraints_json"}.get(key, key)
        setattr(goal, column, json.dumps(value, ensure_ascii=False) if key in {"interests", "constraints"} else value)
    goal.roadmap_json = None
    goal.analysis_json = None
    goal.active = True
    db.query(CareerGoal).filter(CareerGoal.student_id == student.id, CareerGoal.id != goal.id,
                                CareerGoal.active.is_(True)).update({"active": False})
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
    db.query(CareerGoal).filter(CareerGoal.student_id == student.id).update({"analysis_json": None})
    db.commit()
    return {"profile": _profile(student.id, db), "evidence_type": "self_reported_only"}


@router.post("/goals/{goal_id}/roadmap")
def generate_roadmap(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    result = _build(goal, student.id, db)
    _store_new_roadmap(goal, result, db, "generated")
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
    _store_new_roadmap(goal, result, db, "adapted_from_progress")
    db.commit()
    return result


@router.get("/goals/{goal_id}/versions")
def roadmap_versions(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    rows = db.scalars(select(CareerRoadmapVersion).where(
        CareerRoadmapVersion.student_id == student.id,
        CareerRoadmapVersion.goal_id == goal.id,
    ).order_by(CareerRoadmapVersion.version_number.desc()).limit(50)).all()
    return [{"version_number": row.version_number, "change_reason": row.change_reason,
             "created_at": row.created_at.isoformat()} for row in rows]


@router.get("/goals/{goal_id}/versions/{version_number}")
def roadmap_version(goal_id: str, version_number: int, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    row = db.scalar(select(CareerRoadmapVersion).where(
        CareerRoadmapVersion.student_id == student.id,
        CareerRoadmapVersion.goal_id == goal.id,
        CareerRoadmapVersion.version_number == version_number,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Roadmap version not found")
    return json.loads(row.roadmap_json)


@router.get("/goals/{goal_id}/assessments")
def assessment_history(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    _owned_goal(goal_id, student, db)
    attempts = db.scalars(select(LearningAssessmentAttempt).where(
        LearningAssessmentAttempt.student_id == student.id,
        LearningAssessmentAttempt.answered_at.is_not(None),
    ).order_by(LearningAssessmentAttempt.answered_at.desc()).limit(100)).all()
    return [{"attempt_id": item.id, "topic": item.topic, "correct": bool(item.is_correct),
             "score_percent": 100 if item.is_correct else 0, "evidence_type": "server_scored_objective",
             "completed_at": item.answered_at.isoformat() if item.answered_at else None}
            for item in attempts]


@router.post("/goals/{goal_id}/analysis")
def analyze_goal(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    gaps = skill_gaps(list(CAREERS[goal.career_key]["skills"]), _profile(student.id, db), _demonstrated(student.id, db))
    current_plan = json.loads(goal.roadmap_json) if goal.roadmap_json else {}
    progress = current_plan.get("progress", {})
    analysis = analyze_skill_gaps(goal=_goal_json(goal), profile=_profile(student.id, db), gaps=gaps,
                                  progress=progress)
    goal.analysis_json = json.dumps(analysis, ensure_ascii=False)
    db.commit()
    return analysis


@router.get("/goals/{goal_id}/analysis")
def get_goal_analysis(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    return json.loads(goal.analysis_json) if goal.analysis_json else None


@router.get("/goals/{goal_id}/saved-resources")
def saved_resources(goal_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    rows = db.scalars(select(CareerSavedResource).where(
        CareerSavedResource.student_id == student.id, CareerSavedResource.goal_id == goal.id,
    ).order_by(CareerSavedResource.created_at.desc())).all()
    return [{"id": row.id, "resource_url": row.resource_url, "title": row.title,
             "kind": row.kind, "free": row.free, "created_at": row.created_at.isoformat()} for row in rows]


@router.post("/goals/{goal_id}/saved-resources", status_code=status.HTTP_201_CREATED)
def save_resource(goal_id: str, payload: SaveResourceInput,
                  student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    plan = json.loads(goal.roadmap_json) if goal.roadmap_json else _build(goal, student.id, db)
    resource = next((entry for phase in plan["phases"] for entry in phase["resources"]
                     if entry["url"] == payload.resource_url), None)
    if resource is None:
        raise HTTPException(status_code=404, detail="Resource is not in this roadmap's curated catalog")
    row = db.scalar(select(CareerSavedResource).where(
        CareerSavedResource.student_id == student.id, CareerSavedResource.goal_id == goal.id,
        CareerSavedResource.resource_url == resource["url"],
    ))
    if row is None:
        row = CareerSavedResource(student_id=student.id, goal_id=goal.id, resource_url=resource["url"],
                                  title=resource["title"], kind=resource["kind"], free=resource["free"])
        db.add(row)
        db.commit()
        db.refresh(row)
    return {"id": row.id, "resource_url": row.resource_url, "title": row.title,
            "kind": row.kind, "free": row.free, "created_at": row.created_at.isoformat()}


@router.delete("/goals/{goal_id}/saved-resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_saved_resource(goal_id: str, resource_id: str,
                          student: Student = Depends(current_student), db: Session = Depends(get_db)):
    goal = _owned_goal(goal_id, student, db)
    row = db.scalar(select(CareerSavedResource).where(
        CareerSavedResource.student_id == student.id, CareerSavedResource.goal_id == goal.id,
        CareerSavedResource.id == resource_id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Saved resource not found")
    db.delete(row)
    db.commit()


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
