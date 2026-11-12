"""Authenticated multi-question adaptive quizzes over existing assessment tables."""
import json
from collections import defaultdict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.assessments import _progress_for, _recent_outcomes
from backend.app.api.auth import current_student
from backend.app.db.models import LearningAssessmentAttempt, LearningProgress, LearningSession, Student, utc_now
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import normalize_topic, recommend
from backend.app.services.ai_quiz import generate_quiz_questions
from backend.app.services.quiz_engine import (
    CATALOG, SUBJECTS, QuizQuestion, answer_is_valid, available_questions, grade_answer, localized,
    localized_recommendation,
)

router = APIRouter(prefix="/quizzes", tags=["adaptive quizzes"])
LANGUAGES = {"english", "telugu", "mixed"}
DIFFICULTIES = {"beginner", "intermediate", "advanced", "adaptive"}


class CreateQuizRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    difficulty: str = "adaptive"
    language: str = "mixed"
    question_count: int = Field(default=2, ge=1, le=6)

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be blank")
        return value

    @field_validator("difficulty")
    @classmethod
    def valid_difficulty(cls, value: str) -> str:
        value = value.casefold()
        if value not in DIFFICULTIES:
            raise ValueError("Difficulty must be beginner, intermediate, advanced, or adaptive")
        return value

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        value = value.casefold()
        if value not in LANGUAGES:
            raise ValueError("Language must be english, telugu, or mixed")
        return value


class QuizAnswer(BaseModel):
    attempt_id: str = Field(min_length=36, max_length=36)
    answer: str = Field(min_length=1, max_length=500)

    @field_validator("answer")
    @classmethod
    def clean_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Answer cannot be blank")
        return value


class SubmitQuizRequest(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def unique_attempts(self):
        ids = [answer.attempt_id for answer in self.answers]
        if len(ids) != len(set(ids)):
            raise ValueError("Each quiz question must have one answer")
        return self


def _metadata(attempt: LearningAssessmentAttempt) -> dict | None:
    try:
        data = json.loads(attempt.options_json)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("quiz_id"), str) else None


def _question_payload(attempt: LearningAssessmentAttempt, meta: dict) -> dict:
    return {
        "attempt_id": attempt.id,
        "question_id": meta["content_id"],
        "position": meta["position"],
        "type": meta["type"],
        "difficulty": meta["difficulty"],
        "source": meta["source"],
        "prompt": meta["prompt"],
        "options": meta["options"],
    }


def _load_quiz(db: Session, student_id: str, quiz_id: str, lock: bool = False):
    stmt = (select(LearningAssessmentAttempt)
        .where(LearningAssessmentAttempt.student_id == student_id)
        .order_by(LearningAssessmentAttempt.issued_at, LearningAssessmentAttempt.id))
    if lock:
        stmt = stmt.with_for_update()
    attempts = db.scalars(stmt).all()
    items = [(attempt, _metadata(attempt)) for attempt in attempts]
    owned = [(attempt, meta) for attempt, meta in items if meta and meta["quiz_id"] == quiz_id]
    return owned


def _result_rows(owned: list[tuple[LearningAssessmentAttempt, dict]]) -> list[dict]:
    rows = []
    for attempt, meta in owned:
        _, localized_options, _ = localized(_question_from_meta(meta), meta["language"])
        answer_text = attempt.submitted_answer or ""
        rows.append({
            "attempt_id": attempt.id,
            "question_id": meta["content_id"],
            "position": meta["position"],
            "type": meta["type"],
            "prompt": meta["prompt"],
            "answer": answer_text,
            "is_correct": attempt.is_correct,
            "correct_answer": meta["accepted"][0],
            "explanation": meta["explanation"],
            "options": localized_options,
        })
    return rows


def _question_from_meta(meta: dict) -> QuizQuestion:
    # Small formatter object used only to retain shared localization behavior.
    return QuizQuestion(
        id=meta["content_id"], topic=meta["topic"], question_type=meta["type"],
        difficulty=meta["difficulty"], prompt_en=meta["prompt_en"], prompt_te=meta["prompt_te"],
        choices=tuple(tuple(choice) for choice in meta["choices"]), accepted=tuple(meta["accepted"]),
        explanation_en=meta["explanation_en"], explanation_te=meta["explanation_te"], source=meta["source"],
    )


def _summary(owned: list[tuple[LearningAssessmentAttempt, dict]]) -> dict:
    meta = owned[0][1]
    total = len(owned)
    correct = sum(attempt.is_correct is True for attempt, _ in owned)
    mastery = round(100 * correct / total, 1) if total else 0
    return {
        "quiz_id": meta["quiz_id"], "session_id": owned[0][0].session_id,
        "subject": meta["subject"], "topic": meta["topic"], "language": meta["language"],
        "difficulty": meta["difficulty"], "adaptive_difficulty": meta["adaptive_difficulty"],
        "source": meta["source"], "question_count": total, "score": correct,
        "mastery_score": mastery, "completed": all(attempt.submitted_answer is not None for attempt, _ in owned),
        "issued_at": owned[0][0].issued_at, "answered_at": max((a.answered_at for a, _ in owned if a.answered_at), default=None),
    }


@router.get("/catalog")
def quiz_catalog(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    del db
    return [{"subject": SUBJECTS[key], "topic": key, "question_count": len(items),
             "difficulties": sorted({item.difficulty for item in items})}
            for key, items in CATALOG.items()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_quiz(payload: CreateQuizRequest, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    topic_key = normalize_topic(payload.topic)
    subject = SUBJECTS.get(topic_key, "General Learning")

    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student.id,
        LearningProgress.normalized_topic_key == topic_key,
    ).order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc()))
    if payload.difficulty == "adaptive":
        policy = recommend(progress.evidence_attempts if progress else 0,
                           progress.correct_attempts if progress else 0,
                           progress.incorrect_attempts if progress else 0,
                           _recent_outcomes(student.id, topic_key, db))
        difficulty = policy.difficulty
        adaptive_difficulty = True
    else:
        difficulty = payload.difficulty
        adaptive_difficulty = False
    pool = available_questions(topic_key, difficulty)
    provider_failure: HTTPException | None = None
    try:
        chosen = generate_quiz_questions(
            topic=payload.topic.strip(), difficulty=difficulty,
            language=payload.language, question_count=payload.question_count,
        )
    except HTTPException as exc:
        provider_failure = exc
        chosen = None
    if chosen is None:
        if len(pool) < payload.question_count:
            if provider_failure is not None:
                raise provider_failure
            raise HTTPException(status_code=503, detail="Live quiz generation is unavailable, and this topic has no curated fallback.")
        start = progress.evidence_attempts % len(pool) if progress else 0
        ordered = pool[start:] + pool[:start]
        chosen = ordered[:payload.question_count]
    quiz_id = str(uuid4())
    session = LearningSession(student_id=student.id, language=payload.language, topic=payload.topic.strip())
    db.add(session)
    db.flush()
    result_questions = []
    sources = set()
    for position, question in enumerate(chosen, 1):
        prompt, options, explanation = localized(question, payload.language)
        sources.add(question.source)
        meta = {
            "quiz_id": quiz_id, "content_id": question.id, "position": position,
            "subject": subject, "topic": question.topic, "language": payload.language,
            "type": question.question_type, "difficulty": question.difficulty,
            "adaptive_difficulty": adaptive_difficulty, "prompt": prompt,
            "prompt_en": question.prompt_en, "prompt_te": question.prompt_te,
            "options": options, "choices": [list(choice) for choice in question.choices],
            "accepted": list(question.accepted), "explanation": explanation,
            "explanation_en": question.explanation_en, "explanation_te": question.explanation_te,
            "source": question.source,
        }
        attempt = LearningAssessmentAttempt(
            student_id=student.id, session_id=session.id, topic=payload.topic.strip(),
            normalized_topic_key=topic_key,
            question_id=f"int13:{quiz_id}:{position}:{question.id}", prompt=prompt,
            options_json=json.dumps(meta, ensure_ascii=False), expected_answer=question.accepted[0],
            idempotency_key=str(uuid4()),
        )
        db.add(attempt)
        db.flush()
        result_questions.append(_question_payload(attempt, meta))
    db.commit()
    return {
        "quiz_id": quiz_id, "session_id": session.id, "subject": subject,
        "topic": payload.topic.strip(), "language": payload.language,
        "difficulty": difficulty, "adaptive_difficulty": adaptive_difficulty,
        "source": next(iter(sources)) if len(sources) == 1 else "mixed",
        "questions": result_questions,
    }


@router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: str, payload: SubmitQuizRequest,
                student: Student = Depends(current_student), db: Session = Depends(get_db)):
    owned = _load_quiz(db, student.id, quiz_id, lock=True)
    if not owned:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    expected_ids = {attempt.id for attempt, _ in owned}
    submitted_ids = {item.attempt_id for item in payload.answers}
    if submitted_ids != expected_ids:
        raise HTTPException(status_code=422, detail="Submit exactly one answer for every question in this quiz.")
    answer_by_id = {item.attempt_id: item.answer for item in payload.answers}
    completed = all(attempt.submitted_answer is not None for attempt, _ in owned)
    if completed:
        if any(attempt.submitted_answer.casefold() != answer_by_id[attempt.id].casefold() for attempt, _ in owned):
            raise HTTPException(status_code=409, detail="This quiz was already submitted with different answers.")
        result = _summary(owned)
        result["replayed"] = True
        result["questions"] = _result_rows(owned)
        return result

    if any(attempt.submitted_answer is not None for attempt, _ in owned):
        raise HTTPException(status_code=409, detail="This quiz is in an incomplete submission state and cannot be resubmitted.")
    for attempt, meta in owned:
        question = _question_from_meta(meta)
        answer = answer_by_id[attempt.id]
        if not answer_is_valid(question, answer):
            raise HTTPException(status_code=422, detail=f"Choose one of the available options for question {meta['position']}.")

    now = utc_now()
    for attempt, meta in owned:
        answer = answer_by_id[attempt.id]
        correct = grade_answer(_question_from_meta(meta), answer)
        progress = _progress_for(student.id, attempt.normalized_topic_key, attempt.topic, db)
        attempt.submitted_answer = answer
        attempt.answered_at = now
        attempt.is_correct = correct
        progress.evidence_attempts += 1
        progress.attempts = progress.evidence_attempts
        if correct:
            progress.correct_attempts += 1
        else:
            progress.incorrect_attempts += 1
        progress.mastery_score = round(100 * progress.correct_attempts / progress.evidence_attempts, 1)
        progress.evidence_status = "assessed"
        progress.last_assessed_at = now
        progress.updated_at = now
        attempt.feedback = ("Correct. " if correct else "Not quite. ") + meta["explanation"]
    db.commit()
    owned = _load_quiz(db, student.id, quiz_id)
    result = _summary(owned)
    result["replayed"] = False
    result["questions"] = _result_rows(owned)
    policy = recommend(
        db.scalar(select(LearningProgress.evidence_attempts).where(
            LearningProgress.student_id == student.id,
            LearningProgress.normalized_topic_key == owned[0][0].normalized_topic_key,
        )) or 0,
        db.scalar(select(LearningProgress.correct_attempts).where(
            LearningProgress.student_id == student.id,
            LearningProgress.normalized_topic_key == owned[0][0].normalized_topic_key,
        )) or 0,
        db.scalar(select(LearningProgress.incorrect_attempts).where(
            LearningProgress.student_id == student.id,
            LearningProgress.normalized_topic_key == owned[0][0].normalized_topic_key,
        )) or 0,
        _recent_outcomes(student.id, owned[0][0].normalized_topic_key, db),
    )
    result["topic_recommendation"] = localized_recommendation(
        policy.strategy, policy.recommendation, owned[0][1]["language"]
    )
    return result


@router.get("/history")
def quiz_history(student: Student = Depends(current_student), db: Session = Depends(get_db),
                 limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0)):
    attempts = db.scalars(select(LearningAssessmentAttempt).where(
        LearningAssessmentAttempt.student_id == student.id
    ).order_by(LearningAssessmentAttempt.issued_at.desc(), LearningAssessmentAttempt.id.desc())).all()
    grouped = defaultdict(list)
    for attempt in attempts:
        meta = _metadata(attempt)
        if meta:
            grouped[meta["quiz_id"]].append((attempt, meta))
    summaries = [_summary(owned) for owned in grouped.values()]
    summaries.sort(key=lambda item: item["issued_at"], reverse=True)
    return summaries[offset:offset + limit]


@router.get("/{quiz_id}")
def get_quiz(quiz_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    owned = _load_quiz(db, student.id, quiz_id)
    if not owned:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    summary = _summary(owned)
    summary["questions"] = [_question_payload(attempt, meta) for attempt, meta in owned]
    return summary


@router.get("/{quiz_id}/results")
def quiz_results(quiz_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    owned = _load_quiz(db, student.id, quiz_id)
    if not owned:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if not all(attempt.submitted_answer is not None for attempt, _ in owned):
        raise HTTPException(status_code=409, detail="Submit the quiz before viewing explanations.")
    result = _summary(owned)
    result["questions"] = _result_rows(owned)
    return result
