"""Phase 2 contract and ownership regression tests."""
import json

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.api.future_seeker import ReflectionInput
from backend.app.db.base import Base
from backend.app.db.models import FutureSeekerReflection, Student


def test_reflection_input_is_illustrative_and_bounded():
    good = dict(version=1, careerId="scientist", completedSteps=2,
                observedSkills=["Observation"], source="illustrative-simulation")
    assert ReflectionInput(**good).careerId == "scientist"
    for changes in (
        {"source": "verified"}, {"careerId": "administrator"},
        {"completedSteps": -1}, {"observedSkills": ["A", "A"]},
        {"observedSkills": ["x" * 81]}, {"version": 2},
        {"unexpected": "field"},
    ):
        with pytest.raises(ValidationError):
            ReflectionInput(**{**good, **changes})


def test_reflection_is_owned_by_student_and_stores_only_reflective_skills():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        a = Student(email="student-a@example.invalid", display_name="A")
        b = Student(email="student-b@example.invalid", display_name="B")
        db.add_all([a, b])
        db.flush()
        row = FutureSeekerReflection(
            student_id=a.id, career_id="scientist", completed_steps=1,
            observed_skills_json=json.dumps(["Observation"]),
            source="illustrative-simulation",
        )
        db.add(row)
        db.commit()
        assert db.scalar(select(FutureSeekerReflection).where(
            FutureSeekerReflection.student_id == a.id)) is not None
        assert db.scalar(select(FutureSeekerReflection).where(
            FutureSeekerReflection.student_id == b.id)) is None
    engine.dispose()
