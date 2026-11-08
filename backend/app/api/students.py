"""Authenticated student profile and learning preferences."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import Course, LearningAssessmentAttempt, LearningProgress, LearningSession, Student, StudentPreferences
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import LearningActivity, StudentLearningProfile, TopicProficiency, normalize_topic, recommend

router = APIRouter(prefix="/students/me", tags=["students"])


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    display_name: str


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)

    @field_validator("display_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Display name cannot be blank")
        return value


class PreferencesUpdate(BaseModel):
    preferred_language: Literal["telugu", "english", "mixed"] = "mixed"
    learning_level: Literal["beginner", "intermediate", "advanced"] = "beginner"
    learning_pace: Literal["slow", "steady", "fast"] = "steady"
    learning_goal: str | None = Field(default=None, max_length=300)

    @field_validator("learning_goal")
    @classmethod
    def normalize_goal(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PreferencesResponse(PreferencesUpdate):
    model_config = ConfigDict(from_attributes=True)


class TopicProficiencyResponse(BaseModel):
    subject: str | None
    topic: str
    mastery_score: float
    evidence_attempts: int
    difficulty: Literal["beginner", "intermediate", "advanced"]
    strategy: str
    recommendation: str
    revision_recommended: bool
    last_activity_at: datetime | None


class LearningActivityResponse(BaseModel):
    topic: str
    outcome: Literal["correct", "incorrect"]
    occurred_at: datetime


class LearningProfileResponse(BaseModel):
    preferred_language: Literal["telugu", "english", "mixed"]
    learning_pace: Literal["slow", "steady", "fast"]
    proficiencies: list[TopicProficiencyResponse]
    recent_activity: list[LearningActivityResponse]
    revision_topics: list[str]


@router.get("/learning-profile", response_model=LearningProfileResponse)
def get_learning_profile(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    """Return compact evidence-based learner context, never conversation text."""
    preferences = db.get(StudentPreferences, student.id)
    progress_rows = db.scalars(
        select(LearningProgress).where(LearningProgress.student_id == student.id)
        .order_by(LearningProgress.topic, LearningProgress.id)
    ).all()
    attempts = db.execute(
        select(
            LearningAssessmentAttempt.normalized_topic_key,
            LearningAssessmentAttempt.topic,
            LearningAssessmentAttempt.is_correct,
            LearningAssessmentAttempt.answered_at,
        ).where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.is_correct.is_not(None),
        ).order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
    ).all()
    outcomes: dict[str, list[bool]] = {}
    activities: list[LearningActivity] = []
    for key, topic, is_correct, answered_at in attempts:
        if len(outcomes.setdefault(key, [])) < 5:
            outcomes[key].append(bool(is_correct))
        if answered_at is not None and len(activities) < 10:
            activities.append(LearningActivity(topic, "correct" if is_correct else "incorrect", answered_at))

    course_titles: dict[str, str] = {}
    linked = db.execute(
        select(LearningSession.topic, Course.title)
        .join(Course, LearningSession.course_id == Course.id)
        .where(LearningSession.student_id == student.id)
        .order_by(LearningSession.created_at.desc())
    ).all()
    for topic, title in linked:
        course_titles.setdefault(normalize_topic(topic), title)

    proficiencies: list[TopicProficiency] = []
    for item in progress_rows:
        adaptation = recommend(item.evidence_attempts, item.correct_attempts, item.incorrect_attempts,
                               tuple(reversed(outcomes.get(item.normalized_topic_key, [])[:5])))
        proficiencies.append(TopicProficiency(
            topic=item.topic, subject=course_titles.get(item.normalized_topic_key),
            mastery_score=item.mastery_score if item.evidence_attempts else 0.0,
            evidence_attempts=item.evidence_attempts, difficulty=adaptation.difficulty,
            strategy=adaptation.strategy, recommendation=adaptation.recommendation,
            revision_recommended=adaptation.revision_recommended,
            last_activity_at=item.last_assessed_at or item.updated_at,
        ))
    profile = StudentLearningProfile(
        preferred_language=(preferences.preferred_language if preferences else "mixed"),
        learning_pace=(preferences.learning_pace if preferences else "steady"),
        proficiencies=tuple(proficiencies), recent_activity=tuple(activities),
        revision_topics=tuple(item.topic for item in proficiencies if item.revision_recommended),
    )
    return LearningProfileResponse(
        preferred_language=profile.preferred_language, learning_pace=profile.learning_pace,
        proficiencies=[TopicProficiencyResponse.model_validate(item.__dict__) for item in profile.proficiencies],
        recent_activity=[LearningActivityResponse.model_validate(item.__dict__) for item in profile.recent_activity],
        revision_topics=list(profile.revision_topics),
    )


@router.get("", response_model=ProfileResponse)
def get_profile(student: Student = Depends(current_student)):
    return student


@router.patch("", response_model=ProfileResponse)
def update_profile(
    payload: ProfileUpdate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    student.display_name = payload.display_name
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    prefs = db.get(StudentPreferences, student.id)
    if prefs is None:
        return PreferencesResponse()
    return prefs


@router.put("/preferences", response_model=PreferencesResponse)
def put_preferences(
    payload: PreferencesUpdate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    prefs = db.get(StudentPreferences, student.id)
    if prefs is None:
        prefs = StudentPreferences(student_id=student.id)
    prefs.preferred_language = payload.preferred_language
    prefs.learning_level = payload.learning_level
    prefs.learning_pace = payload.learning_pace
    prefs.learning_goal = payload.learning_goal
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs
