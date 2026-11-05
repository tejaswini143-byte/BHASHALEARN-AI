"""Course catalog and ordered lesson endpoints.

BE-05 is a development-only catalog API. Creation requires a logged-in student;
role-based author/admin permissions must be added before public deployment.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import Course, Lesson, Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    language: Literal["telugu", "english", "mixed"] = "mixed"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title cannot be blank")
        return value


class CourseResponse(CourseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    position: int = Field(ge=1)

    @field_validator("title", "content")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value cannot be blank")
        return value


class LessonResponse(LessonCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    course_id: str


@router.get("", response_model=list[CourseResponse])
def list_courses(
    language: Literal["telugu", "english", "mixed"] | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Course).order_by(Course.title, Course.id).offset(offset).limit(limit)
    if language is not None:
        stmt = stmt.where(Course.language == language)
    return db.scalars(stmt).all()


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    _student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    course = Course(**payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: str, db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.get("/{course_id}/lessons", response_model=list[LessonResponse])
def list_lessons(course_id: str, db: Session = Depends(get_db)):
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return db.scalars(select(Lesson).where(Lesson.course_id == course_id).order_by(Lesson.position)).all()


@router.post("/{course_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
def create_lesson(
    course_id: str,
    payload: LessonCreate,
    _student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    lesson = Lesson(course_id=course_id, **payload.model_dump())
    db.add(lesson)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Lesson position already used in this course") from exc
    db.refresh(lesson)
    return lesson


@router.get("/{course_id}/lessons/{lesson_id}", response_model=LessonResponse)
def get_lesson(course_id: str, lesson_id: str, db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if lesson is None or lesson.course_id != course_id:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson
