"""Authenticated, versioned visual lesson catalog API.

Only allowlisted simulations are returned. Arbitrary client-provided scene commands
and unvalidated model output are intentionally not accepted in this phase.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.api.auth import current_student
from backend.app.db.models import Student

router = APIRouter(prefix="/visual-lessons", tags=["visual lessons"])
LessonId = Literal["solar-system", "geometry", "pendulum"]


class BilingualText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    en: str = Field(min_length=1, max_length=500)
    te: str = Field(min_length=1, max_length=500)


class LessonStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: BilingualText
    explanation: BilingualText


class VisualLesson(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: LessonId
    subject: BilingualText
    topic: BilingualText
    title: BilingualText
    description: BilingualText
    objectives: list[BilingualText] = Field(min_length=1, max_length=12)
    takeaways: list[BilingualText] = Field(min_length=1, max_length=12)
    steps: list[LessonStep] = Field(min_length=1, max_length=24)


class LessonEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1] = 1
    lesson: VisualLesson
    scene: dict[str, LessonId]

    @model_validator(mode="after")
    def matching_scene(self):
        if set(self.scene) != {"kind"} or self.scene["kind"] != self.lesson.id:
            raise ValueError("Scene kind must match the lesson id")
        return self


def bilingual(en: str, te: str) -> BilingualText:
    return BilingualText(en=en, te=te)


_CATALOG = (
    VisualLesson(
        id="solar-system",
        subject=bilingual("Space science", "అంతరిక్ష విజ్ఞానం"),
        topic=bilingual("Planetary orbits", "గ్రహ కక్ష్యలు"),
        title=bilingual("A tour of the solar system", "సౌర కుటుంబ యాత్ర"),
        description=bilingual("Explore how planets orbit the Sun.", "గ్రహాలు సూర్యుని చుట్టూ ఎలా తిరుగుతాయో తెలుసుకోండి."),
        objectives=[bilingual("Identify the eight planets.", "ఎనిమిది గ్రహాలను గుర్తించండి.")],
        takeaways=[bilingual("Distant planets generally have longer orbital periods.", "దూరపు గ్రహాలకు సాధారణంగా ఎక్కువ కక్ష్య కాలం ఉంటుంది.")],
        steps=[
            LessonStep(title=bilingual("Meet the Sun", "సూర్యుడిని తెలుసుకోండి"), explanation=bilingual("Gravity holds planets in orbit.", "గురుత్వాకర్షణ గ్రహాలను కక్ష్యలో ఉంచుతుంది.")),
            LessonStep(title=bilingual("Select a planet", "గ్రహాన్ని ఎంచుకోండి"), explanation=bilingual("Compare its orbital period.", "దాని కక్ష్య కాలాన్ని పోల్చండి.")),
        ],
    ),
    VisualLesson(
        id="geometry",
        subject=bilingual("Mathematics", "గణితం"),
        topic=bilingual("3D solid shapes", "త్రిమితీయ ఘన ఆకారాలు"),
        title=bilingual("Inspect 3D shapes", "త్రిమితీయ ఆకారాలను పరిశీలించండి"),
        description=bilingual("Explore a cube, sphere, and cylinder.", "ఘనం, గోళం మరియు స్థూపాన్ని పరిశీలించండి."),
        objectives=[bilingual("Compare shapes and measurements.", "ఆకారాలు మరియు కొలతలను పోల్చండి.")],
        takeaways=[bilingual("Different solids have different surface and volume formulas.", "వేర్వేరు ఘనాలకు వేర్వేరు వైశాల్య, ఘనపరిమాణ సూత్రాలు ఉంటాయి.")],
        steps=[
            LessonStep(title=bilingual("Choose a shape", "ఆకారాన్ని ఎంచుకోండి"), explanation=bilingual("Inspect its surfaces.", "దాని ఉపరితలాలను పరిశీలించండి.")),
            LessonStep(title=bilingual("Change dimensions", "కొలతలను మార్చండి"), explanation=bilingual("Observe how measurements change.", "కొలతలు ఎలా మారుతాయో గమనించండి.")),
        ],
    ),
    VisualLesson(
        id="pendulum",
        subject=bilingual("Physics", "భౌతిక శాస్త్రం"),
        topic=bilingual("Periodic motion", "ఆవర్తన చలనం"),
        title=bilingual("Pendulum motion", "లోలకం చలనం"),
        description=bilingual("Explore the effects of length and gravity.", "పొడవు మరియు గురుత్వాకర్షణ ప్రభావాన్ని పరిశీలించండి."),
        objectives=[bilingual("Compare pendulum periods.", "లోలకం ఆవర్తన కాలాలను పోల్చండి.")],
        takeaways=[bilingual("Longer pendulums have longer periods at fixed gravity.", "ఒకే గురుత్వంలో పొడవైన లోలకాలకు ఎక్కువ ఆవర్తన కాలం ఉంటుంది.")],
        steps=[
            LessonStep(title=bilingual("Set length", "పొడవును సెట్ చేయండి"), explanation=bilingual("Adjust the string length.", "తాడు పొడవును మార్చండి.")),
            LessonStep(title=bilingual("Compare gravity", "గురుత్వాన్ని పోల్చండి"), explanation=bilingual("Observe the period change.", "ఆవర్తన కాలంలో మార్పును గమనించండి.")),
        ],
    ),
)
CATALOG = {item.id: LessonEnvelope(lesson=item, scene={"kind": item.id}) for item in _CATALOG}


@router.get("", response_model=list[LessonEnvelope])
def list_visual_lessons(_student: Student = Depends(current_student)):
    return list(CATALOG.values())


@router.get("/{lesson_id}", response_model=LessonEnvelope)
def get_visual_lesson(lesson_id: str, _student: Student = Depends(current_student)):
    lesson = CATALOG.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Visual lesson not found")
    return lesson
