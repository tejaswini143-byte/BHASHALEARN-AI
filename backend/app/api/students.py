"""Authenticated student profile and learning preferences."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import Student, StudentPreferences
from backend.app.db.session import get_db

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
    learning_goal: str | None = Field(default=None, max_length=300)

    @field_validator("learning_goal")
    @classmethod
    def normalize_goal(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class PreferencesResponse(PreferencesUpdate):
    pass


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
    prefs.learning_goal = payload.learning_goal
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs
