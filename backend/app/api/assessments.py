"""Authenticated, session-owned, idempotent objective assessment flow."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import (
    LearningAssessmentAttempt,
    LearningProgress,
    Student,
    StudentPreferences,
    new_id,
    utc_now,
)
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import (
    choose_adaptation,
    mastery_category,
    normalize_topic,
    record_scored_outcome,
)
from backend.app.services.assessment_bank import make_assessment

router = APIRouter(prefix="/tutor/sessions", tags=["adaptive assessments"])


class AssessmentIssuedResponse(BaseModel):
    assessment_id: str
    topic: str
    question: str
    choices: dict[str, str]
    language: Literal["english", "telugu", "mixed"]
    created_at: datetime


class AssessmentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=16)

    @field_validator("answer")
    @classmethod
    def normalize_answer(cls, value: str) -> str:
        return value.strip().casefold()


class AssessmentResultResponse(BaseModel):
    assessment_id: str
    topic: str
    question: str
    submitted_answer: str
    outcome: Literal["correct", "incorrect", "ambiguous"]
    correct_answer: str
    feedback: str
    mastery_score: float | None
    mastery_category: str
    evidence_count: int
    recommended_difficulty: str
    teaching_strategy: str


def _ensure_progress(db: Session, student_id: str, topic: str, topic_key: str) -> LearningProgress:
    dialect = db.get_bind().dialect.name
    values = {
        "id": new_id(),
        "student_id": student_id,
        "topic": topic,
        "topic_key": topic_key,
        "mastery_score": 0.0,
        "attempts": 0,
        "evidence_count": 0,
        "correct_attempts": 0,
        "incorrect_attempts": 0,
        "correct_streak": 0,
        "updated_at": utc_now(),
    }
    if dialect == "postgresql":
        statement = pg_insert(LearningProgress).values(**values).on_conflict_do_nothing(
            index_elements=[LearningProgress.student_id, LearningProgress.topic_key]
        )
    elif dialect == "sqlite":
        statement = sqlite_insert(LearningProgress).values(**values).on_conflict_do_nothing(
            index_elements=[LearningProgress.student_id, LearningProgress.topic_key]
        )
    else:
        raise HTTPException(status_code=503, detail="Assessment storage is unavailable for this database.")
    db.execute(statement)
    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student_id,
        LearningProgress.topic_key == topic_key,
    ).with_for_update())
    if progress is None:
        raise HTTPException(status_code=500, detail="Could not initialize topic progress.")
    return progress


def _language_feedback(language: str, outcome: str, expected: str) -> str:
    if outcome == "correct":
        return {
            "telugu": "సరైన సమాధానం. ఈ సమాధానం topic understandingకి ఒక learning evidenceగా నమోదు అయింది.",
            "mixed": "సరైన సమాధానం. This objective check is recorded as learning evidence.",
        }.get(language, "Correct. This objective check is recorded as learning evidence.")
    if outcome == "ambiguous":
        return {
            "telugu": "ఈ సమాధానాన్ని score చేయలేదు. మీరు సిద్ధంగా ఉన్నప్పుడు మళ్లీ ప్రయత్నించండి.",
            "mixed": "ఈ answerను score చేయలేదు. You can try again when ready.",
        }.get(language, "This answer was not scored. You can try again when ready.")
    return {
        "telugu": f"ఇంకా సరిపోలలేదు. సరైన ఎంపిక {expected}. ఈ అంశాన్ని మరో ఉదాహరణతో మళ్లీ చూద్దాం.",
        "mixed": f"ఇంకా సరిపోలలేదు. Correct option {expected}. ఈ conceptను మరో exampleతో చూద్దాం.",
    }.get(language, f"Not quite. The correct option is {expected}. Review the concept with another example.")


def _serialize_result(attempt: LearningAssessmentAttempt) -> AssessmentResultResponse:
    return AssessmentResultResponse(
        assessment_id=attempt.id,
        topic=attempt.topic,
        question=attempt.question,
        submitted_answer=attempt.submitted_answer or "unsure",
        outcome=attempt.outcome,
        correct_answer=attempt.expected_answer,
        feedback=attempt.feedback or "Answer recorded.",
        mastery_score=attempt.result_mastery_score,
        mastery_category=attempt.result_category or "not_assessed",
        evidence_count=attempt.result_evidence_count or 0,
        recommended_difficulty=attempt.result_difficulty or "beginner",
        teaching_strategy=attempt.result_strategy or "diagnostic_question",
    )


@router.post("/{session_id}/assessments", response_model=AssessmentIssuedResponse, status_code=201)
def issue_assessment(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = owned_session(session_id, student, db)
    topic, topic_key = normalize_topic(session.topic)
    preferences = db.get(StudentPreferences, student.id)
    language = preferences.preferred_language if preferences else session.language
    try:
        progress = _ensure_progress(db, student.id, topic, topic_key)
        pending = db.scalar(select(LearningAssessmentAttempt).where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.session_id == session_id,
            LearningAssessmentAttempt.topic_key == topic_key,
            LearningAssessmentAttempt.outcome == "pending",
        ).order_by(LearningAssessmentAttempt.created_at.desc()).limit(1))
        if pending is not None:
            db.commit()
            return AssessmentIssuedResponse(
                assessment_id=pending.id,
                topic=pending.topic,
                question=pending.question,
                choices=pending.choices,
                language=pending.language,
                created_at=pending.created_at,
            )
        sequence = db.scalar(select(func.count(LearningAssessmentAttempt.id)).where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.topic_key == topic_key,
        )) or 0
        question = make_assessment(topic, int(sequence), language)
        if question is None:
            db.rollback()
            raise HTTPException(status_code=422, detail="Objective practice is not configured for this topic yet.")
        created_at = utc_now()
        previous_created_at = db.scalar(select(func.max(LearningAssessmentAttempt.created_at)).where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.topic_key == topic_key,
        ))
        if previous_created_at is not None:
            if previous_created_at.tzinfo is None:
                previous_created_at = previous_created_at.replace(tzinfo=timezone.utc)
            if created_at <= previous_created_at:
                created_at = previous_created_at + timedelta(microseconds=1)
        attempt = LearningAssessmentAttempt(
            id=new_id(),
            student_id=student.id,
            session_id=session_id,
            progress_id=progress.id,
            topic=topic,
            topic_key=topic_key,
            language=language,
            question_code=question.question_code,
            question=question.question,
            choices=question.choices,
            expected_answer=question.expected_answer,
            misconception_map=question.misconception_map,
            outcome="pending",
            created_at=created_at,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        return AssessmentIssuedResponse(
            assessment_id=attempt.id,
            topic=topic,
            question=attempt.question,
            choices=attempt.choices,
            language=language,
            created_at=attempt.created_at,
        )
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise


@router.post("/{session_id}/assessments/{assessment_id}/answer", response_model=AssessmentResultResponse)
def submit_assessment_answer(
    session_id: str,
    assessment_id: str,
    payload: AssessmentAnswer,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    owned_session(session_id, student, db)
    try:
        attempt = db.scalar(select(LearningAssessmentAttempt).where(
            LearningAssessmentAttempt.id == assessment_id,
            LearningAssessmentAttempt.session_id == session_id,
            LearningAssessmentAttempt.student_id == student.id,
        ).with_for_update())
        if attempt is None:
            raise HTTPException(status_code=404, detail="Assessment not found.")
        if payload.answer not in {"a", "b", "c", "d", "unsure", "?"}:
            raise HTTPException(status_code=422, detail="Choose A, B, C, D, or unsure.")
        normalized_answer = "unsure" if payload.answer == "?" else payload.answer
        if attempt.outcome != "pending":
            if attempt.submitted_answer != normalized_answer:
                raise HTTPException(status_code=409, detail="This assessment already has a different recorded answer.")
            return _serialize_result(attempt)

        progress = db.scalar(select(LearningProgress).where(
            LearningProgress.id == attempt.progress_id,
            LearningProgress.student_id == student.id,
            LearningProgress.topic_key == attempt.topic_key,
        ).with_for_update())
        if progress is None:
            raise HTTPException(status_code=409, detail="Topic progress is no longer available.")

        if normalized_answer == "unsure":
            outcome = "ambiguous"
            misconception = None
        elif normalized_answer.upper() == attempt.expected_answer:
            outcome = "correct"
            misconception = None
        else:
            outcome = "incorrect"
            misconception = attempt.misconception_map.get(normalized_answer.upper(), "answer_error")

        attempt.submitted_answer = normalized_answer
        attempt.outcome = outcome
        attempt.misconception_code = misconception
        if outcome in {"correct", "incorrect"}:
            record_scored_outcome(progress, outcome)
        preferences = db.get(StudentPreferences, student.id)
        attempt.feedback = _language_feedback(
            preferences.preferred_language if preferences else "mixed",
            outcome,
            attempt.expected_answer,
        )
        attempt.submitted_at = utc_now()
        db.flush()
        recent = db.scalars(select(LearningAssessmentAttempt).where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.topic_key == attempt.topic_key,
            LearningAssessmentAttempt.outcome.in_(("correct", "incorrect", "ambiguous")),
        ).order_by(LearningAssessmentAttempt.created_at.desc(), LearningAssessmentAttempt.id.desc()).limit(8)).all()
        preferences = db.get(StudentPreferences, student.id)
        adaptation = choose_adaptation(progress, recent, preferences.learning_level if preferences else "beginner")
        attempt.result_mastery_score = float(progress.mastery_score) if progress.evidence_count else None
        attempt.result_evidence_count = progress.evidence_count
        attempt.result_category = mastery_category(progress)
        attempt.result_difficulty = adaptation.recommended_difficulty
        attempt.result_strategy = adaptation.teaching_strategy
        db.commit()
        db.refresh(attempt)
        return _serialize_result(attempt)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
