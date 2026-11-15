"""Authenticated, versioned visual lesson catalog API.

Only allowlisted simulations are returned. Arbitrary client-provided scene commands
and unvalidated model output are intentionally not accepted in this phase.
"""
import json
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.config import get_settings, is_placeholder_secret
from backend.app.db.models import Student, VisualLessonSessionState
from backend.app.db.session import get_db

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
    scene_id: LessonId | None = None


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


class LessonQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: BilingualText
    answer: BilingualText
    explanation: BilingualText


class LessonActivity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instruction: BilingualText
    control: Literal["select-planet", "rotate-shape", "adjust-length", "adjust-gravity", "change-time"]


class GeneratedLesson(VisualLesson):
    questions: list[LessonQuestion] = Field(min_length=1, max_length=8)
    activities: list[LessonActivity] = Field(min_length=1, max_length=8)
    completion_criteria: list[BilingualText] = Field(min_length=1, max_length=8)


class GeneratedScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: LessonId
    parameters: dict[str, object]

    @model_validator(mode="after")
    def supported_parameters(self):
        params = self.parameters
        if self.kind == "solar-system":
            if set(params) != {"time_scale"} or type(params["time_scale"]) is not int or not 0 <= params["time_scale"] <= 100:
                raise ValueError("Solar-system parameters require time_scale from 0 to 100")
        elif self.kind == "geometry":
            shape = params.get("shape")
            if set(params) != {"shape", "size"} or not isinstance(shape, str) or shape not in {"cube", "sphere", "cylinder"}:
                raise ValueError("Geometry parameters require a supported shape and size")
            size = params["size"]
            if isinstance(size, bool) or not isinstance(size, (int, float)) or not 0.25 <= size <= 3:
                raise ValueError("Geometry size must be from 0.25 to 3")
        elif self.kind == "pendulum":
            if set(params) != {"length", "gravity"}:
                raise ValueError("Pendulum parameters require length and gravity")
            length, gravity = params["length"], params["gravity"]
            if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in (length, gravity)):
                raise ValueError("Pendulum parameters must be numeric")
            if not 0.5 <= length <= 3 or not 0.1 <= gravity <= 25:
                raise ValueError("Pendulum parameters are out of range")
        return self


class GeneratedLessonEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[2] = 2
    lesson: GeneratedLesson
    scene: GeneratedScene

    @model_validator(mode="after")
    def matching_scene(self):
        if self.scene.kind != self.lesson.id:
            raise ValueError("Scene kind must match the lesson id")
        if any(step.scene_id not in (None, self.scene.kind) for step in self.lesson.steps):
            raise ValueError("Step scene IDs must match the lesson scene")
        return self


class GenerateLessonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=2, max_length=200)
    language: Literal["english", "telugu", "mixed"] = "english"
    scene_kind: LessonId
    session_id: str = Field(min_length=36, max_length=36)

    @model_validator(mode="after")
    def nonblank_topic(self):
        self.topic = self.topic.strip()
        if not self.topic:
            raise ValueError("Topic cannot be blank")
        return self


def generate_lesson_with_gemini(request: GenerateLessonRequest) -> GeneratedLessonEnvelope:
    settings = get_settings()
    api_key = settings.gemini_api_key.strip()
    if is_placeholder_secret(api_key):
        raise HTTPException(status_code=503, detail="AI provider not configured")
    schema = {
        "version": 2,
        "lesson": {
            "id": request.scene_kind,
            "subject": {"en": "...", "te": "..."}, "topic": {"en": "...", "te": "..."},
            "title": {"en": "...", "te": "..."}, "description": {"en": "...", "te": "..."},
            "objectives": [{"en": "...", "te": "..."}], "takeaways": [{"en": "...", "te": "..."}],
            "steps": [{"title": {"en": "...", "te": "..."}, "explanation": {"en": "...", "te": "..."}, "scene_id": request.scene_kind}],
            "questions": [{"prompt": {"en": "...", "te": "..."}, "answer": {"en": "...", "te": "..."}, "explanation": {"en": "...", "te": "..."}}],
            "activities": [{"instruction": {"en": "...", "te": "..."}, "control": "select-planet"}],
            "completion_criteria": [{"en": "...", "te": "..."}],
        },
        "scene": {"kind": request.scene_kind, "parameters": {}},
    }
    prompt = (
        "Return only one JSON object matching this exact lesson contract. No markdown, HTML, code, or executable content. "
        "Use Unicode Telugu script for te fields and meaningful English for en fields. Keep activities within the supplied "
        "scene controls. Scene parameters must be valid: solar-system {time_scale: integer 0..100}; geometry "
        "{shape: cube|sphere|cylinder, size: number 0.25..3}; pendulum {length: number 0.5..3, gravity: number 0.1..25}. "
        "Every step scene_id must match the selected scene. Keep teaching accurate and age appropriate.\n"
        f"Topic: {json.dumps(request.topic, ensure_ascii=False)}\n"
        f"Preferred language: {request.language}; still provide both languages.\n"
        f"Contract: {json.dumps(schema, ensure_ascii=False)}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
    try:
        with httpx.Client(timeout=35.0) as client:
            response = client.post(
                url,
                headers={"x-goog-api-key": api_key},
                json={"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                     "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json", "maxOutputTokens": 2400}},
            )
        response.raise_for_status()
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        return GeneratedLessonEnvelope.model_validate(parsed)
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        raise HTTPException(status_code=502, detail="Gemini returned an unavailable or invalid lesson") from error


class LessonStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=36, max_length=36)
    envelope: dict[str, object]
    current_step: int = Field(ge=-1, le=23)
    paused: bool
    completed: bool
    interactions: dict[str, str | int | float | bool] = Field(default_factory=dict)
    quiz_responses: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def allowed_interactions(self):
        allowed = {"selected_planet", "time_scale", "shape", "size", "rotation", "length", "gravity"}
        if set(self.interactions) - allowed:
            raise ValueError("Unsupported visual interaction field")
        numeric_bounds = {"time_scale": (0, 100), "size": (0.25, 3), "rotation": (-180, 180), "length": (0.5, 3), "gravity": (0.1, 25)}
        for key, bounds in numeric_bounds.items():
            value = self.interactions.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not bounds[0] <= value <= bounds[1]):
                raise ValueError(f"Visual interaction {key} is out of range")
        if "shape" in self.interactions and self.interactions["shape"] not in {"cube", "sphere", "cylinder"}:
            raise ValueError("Unsupported geometry shape")
        if "selected_planet" in self.interactions and self.interactions["selected_planet"] not in {"mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"}:
            raise ValueError("Unsupported planet selection")
        if any(len(value) > 500 for value in self.quiz_responses):
            raise ValueError("Quiz response is too long")
        return self


def validate_lesson_envelope(value: dict[str, object]) -> LessonEnvelope | GeneratedLessonEnvelope:
    if value.get("version") == 1:
        return LessonEnvelope.model_validate(value)
    if value.get("version") == 2:
        return GeneratedLessonEnvelope.model_validate(value)
    raise HTTPException(status_code=422, detail="Unsupported visual lesson contract version")


def _encode_envelope(value: dict[str, object]) -> tuple[str, str, int]:
    envelope = validate_lesson_envelope(value)
    lesson = envelope.lesson
    return json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False), lesson.id, len(lesson.steps)


def _state_payload(state: VisualLessonSessionState | None) -> dict[str, object] | None:
    if state is None:
        return None
    try:
        envelope = json.loads(state.lesson_json)
        interactions = json.loads(state.interactions_json)
        quiz_responses = json.loads(state.quiz_responses_json)
    except (TypeError, ValueError) as error:
        raise HTTPException(status_code=500, detail="Saved visual lesson state is invalid") from error
    return {
        "session_id": state.session_id, "lesson_id": state.lesson_id, "envelope": envelope,
        "current_step": state.current_step, "paused": state.paused, "completed": state.completed,
        "interactions": interactions, "quiz_responses": quiz_responses,
        "updated_at": state.updated_at,
    }


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


@router.get("/session-state")
def get_visual_lesson_session_state(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    owned_session(session_id, student, db)
    return {"state": _state_payload(db.get(VisualLessonSessionState, session_id))}


@router.get("/{lesson_id}", response_model=LessonEnvelope)
def get_visual_lesson(lesson_id: str, _student: Student = Depends(current_student)):
    lesson = CATALOG.get(lesson_id)
    if lesson is None:
        raise HTTPException(status_code=404, detail="Visual lesson not found")
    return lesson


@router.post("/generate", response_model=GeneratedLessonEnvelope)
def generate_visual_lesson(
    payload: GenerateLessonRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Generate content only; scene parameters are validated before they reach the renderer."""
    owned_session(payload.session_id, student, db)
    envelope = generate_lesson_with_gemini(payload)
    state = db.get(VisualLessonSessionState, payload.session_id)
    if state is None:
        state = VisualLessonSessionState(session_id=payload.session_id)
        db.add(state)
    state.lesson_id = envelope.lesson.id
    state.lesson_json = json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False)
    state.current_step = -1
    state.paused = True
    state.completed = False
    state.interactions_json = json.dumps(envelope.scene.parameters, ensure_ascii=False)
    state.quiz_responses_json = "[]"
    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    return envelope


@router.put("/session-state")
def save_visual_lesson_session_state(
    payload: LessonStateUpdate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    owned_session(payload.session_id, student, db)
    lesson_json, lesson_id, step_count = _encode_envelope(payload.envelope)
    if payload.current_step >= step_count:
        raise HTTPException(status_code=422, detail="Current step is outside the lesson")
    envelope = validate_lesson_envelope(payload.envelope)
    has_generated_questions = isinstance(envelope, GeneratedLessonEnvelope) and bool(envelope.lesson.questions)
    if payload.completed and (payload.current_step != step_count - 1 or has_generated_questions and not payload.quiz_responses):
        raise HTTPException(status_code=422, detail="Lesson completion criteria are not met")
    state = db.get(VisualLessonSessionState, payload.session_id)
    if state is None:
        state = VisualLessonSessionState(session_id=payload.session_id)
        db.add(state)
    state.lesson_id = lesson_id
    state.lesson_json = lesson_json
    state.current_step = payload.current_step
    state.paused = payload.paused
    state.completed = payload.completed
    state.interactions_json = json.dumps(payload.interactions, ensure_ascii=False)
    state.quiz_responses_json = json.dumps(payload.quiz_responses, ensure_ascii=False)
    state.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(state)
    return {"state": _state_payload(state)}
