"""Opt-in, authenticated career reflections. These are not skill certifications."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import FutureSeekerReflection, Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/future-seeker", tags=["future seeker"])
CAREER_IDS = frozenset({"software-engineer", "doctor", "scientist", "entrepreneur"})


class ReflectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=1)
    careerId: str
    completedSteps: int = Field(ge=0, le=20)
    observedSkills: list[str] = Field(max_length=24)
    source: str

    @field_validator("careerId")
    @classmethod
    def supported_career(cls, value: str) -> str:
        if value not in CAREER_IDS:
            raise ValueError("Unsupported career")
        return value

    @field_validator("source")
    @classmethod
    def illustrative_only(cls, value: str) -> str:
        if value != "illustrative-simulation":
            raise ValueError("Reflections cannot be certified")
        return value

    @field_validator("observedSkills")
    @classmethod
    def bounded_skills(cls, value: list[str]) -> list[str]:
        if any(not skill.strip() or len(skill) > 80 for skill in value) or len(set(value)) != len(value):
            raise ValueError("Invalid or duplicate reflective skills")
        return value


def serialize(row: FutureSeekerReflection) -> dict:
    return {
        "id": row.id, "version": 1, "careerId": row.career_id,
        "completedSteps": row.completed_steps,
        "observedSkills": json.loads(row.observed_skills_json),
        "source": row.source, "createdAt": row.created_at.isoformat(),
    }


@router.post("/reflections", status_code=status.HTTP_201_CREATED)
def create_reflection(
    payload: ReflectionInput,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    row = FutureSeekerReflection(
        student_id=student.id, career_id=payload.careerId,
        completed_steps=payload.completedSteps,
        observed_skills_json=json.dumps(payload.observedSkills),
        source="illustrative-simulation",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return serialize(row)


@router.get("/reflections")
def list_reflections(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(FutureSeekerReflection)
        .where(FutureSeekerReflection.student_id == student.id)
        .order_by(FutureSeekerReflection.created_at.desc(), FutureSeekerReflection.id.desc())
        .limit(100)
    ).all()
    return [serialize(row) for row in rows]


@router.delete("/reflections/{reflection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reflection(
    reflection_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    row = db.scalar(select(FutureSeekerReflection).where(
        FutureSeekerReflection.id == reflection_id,
        FutureSeekerReflection.student_id == student.id,
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Reflection not found")
    db.delete(row)
    db.commit()
