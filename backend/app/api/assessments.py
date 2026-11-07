"""Server-issued objective assessments and evidence-backed mastery updates."""
import json
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import LearningAssessmentAttempt, LearningProgress, Student, utc_now
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import normalize_topic, recommend
from backend.app.services.assessment_bank import question_for

router = APIRouter(prefix="/assessments", tags=["adaptive assessments"])


class IssueResponse(BaseModel):
    attempt_id: str
    topic: str
    question_id: str
    prompt: str
    options: list[str]
    issued_at: datetime


class AnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=500)

    @field_validator("answer")
    @classmethod
    def clean_answer(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Answer cannot be blank")
        return value


class AnswerResponse(BaseModel):
    attempt_id: str
    topic: str
    answer: str
    is_correct: bool | None
    ambiguous: bool
    feedback: str
    mastery_score: float | None
    evidence_attempts: int
    correct_attempts: int
    incorrect_attempts: int
    difficulty: str
    strategy: str
    recommendation: str
    reason: str
    revision_recommended: bool
    replayed: bool = False


def _progress_for(student_id: str, topic_key: str, topic: str, db: Session) -> LearningProgress:
    progress = db.scalar(
        select(LearningProgress)
        .where(LearningProgress.student_id == student_id, LearningProgress.normalized_topic_key == topic_key)
        .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc())
        .with_for_update()
    )
    if progress is None:
        progress = LearningProgress(
            student_id=student_id,
            topic=topic,
            normalized_topic_key=topic_key,
            mastery_score=0,
            attempts=0,
            evidence_attempts=0,
            correct_attempts=0,
            incorrect_attempts=0,
            ambiguous_attempts=0,
            evidence_status="unassessed",
        )
        db.add(progress)
        db.flush()
    return progress


def _recent_outcomes(student_id: str, topic_key: str, db: Session) -> tuple[bool, ...]:
    attempts = db.scalars(
        select(LearningAssessmentAttempt.is_correct)
        .where(
            LearningAssessmentAttempt.student_id == student_id,
            LearningAssessmentAttempt.normalized_topic_key == topic_key,
            LearningAssessmentAttempt.is_correct.is_not(None),
        )
        .order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(5)
    ).all()
    return tuple(bool(value) for value in reversed(attempts))


@router.post("/sessions/{session_id}/issue", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
def issue_assessment(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = owned_session(session_id, student, db)
    topic_key = normalize_topic(session.topic)
    progress = db.scalar(
        select(LearningProgress)
        .where(LearningProgress.student_id == student.id, LearningProgress.normalized_topic_key == topic_key)
        .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc())
    )
    sequence = (progress.evidence_attempts if progress else 0) + 1
    question = question_for(topic_key, sequence)
    if question is None:
        raise HTTPException(status_code=422, detail="Objective assessments are not available for this topic yet.")
    attempt = LearningAssessmentAttempt(
        student_id=student.id,
        session_id=session.id,
        topic=session.topic,
        normalized_topic_key=topic_key,
        question_id=question.id,
        prompt=question.prompt,
        options_json=json.dumps(question.options),
        expected_answer=question.answer,
        idempotency_key=str(uuid4()),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return IssueResponse(
        attempt_id=attempt.id,
        topic=attempt.topic,
        question_id=attempt.question_id,
        prompt=attempt.prompt,
        options=list(question.options),
        issued_at=attempt.issued_at,
    )


@router.post("/{attempt_id}/answer", response_model=AnswerResponse)
def submit_answer(
    attempt_id: str,
    payload: AnswerRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    attempt = db.scalar(
        select(LearningAssessmentAttempt)
        .where(LearningAssessmentAttempt.id == attempt_id, LearningAssessmentAttempt.student_id == student.id)
        .with_for_update()
    )
    if attempt is None:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")
    owned_session(attempt.session_id, student, db)

    answer = payload.answer.strip()
    if attempt.submitted_answer is not None:
        if attempt.submitted_answer.casefold() != answer.casefold():
            raise HTTPException(status_code=409, detail="This assessment was already submitted with a different answer.")
        progress = db.scalar(
            select(LearningProgress)
            .where(LearningProgress.student_id == student.id, LearningProgress.normalized_topic_key == attempt.normalized_topic_key)
            .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc())
        )
        adaptation = recommend(progress.evidence_attempts if progress else 0, progress.correct_attempts if progress else 0, progress.incorrect_attempts if progress else 0,
                                _recent_outcomes(student.id, attempt.normalized_topic_key, db))
        return AnswerResponse(
            attempt_id=attempt.id, topic=attempt.topic, answer=answer, is_correct=attempt.is_correct,
            ambiguous=attempt.is_correct is None, feedback=attempt.feedback or "", mastery_score=progress.mastery_score if progress and progress.evidence_attempts else None,
            evidence_attempts=progress.evidence_attempts if progress else 0, correct_attempts=progress.correct_attempts if progress else 0,
            incorrect_attempts=progress.incorrect_attempts if progress else 0, difficulty=adaptation.difficulty,
            strategy=adaptation.strategy, recommendation=adaptation.recommendation,
            reason=adaptation.reason, revision_recommended=adaptation.revision_recommended, replayed=True,
        )

    options = json.loads(attempt.options_json)
    selected = next((item for item in options if item.casefold() == answer.casefold()), None)
    progress = _progress_for(student.id, attempt.normalized_topic_key, attempt.topic, db)
    attempt.submitted_answer = answer
    attempt.answered_at = utc_now()
    if selected is None:
        progress.ambiguous_attempts += 1
        attempt.is_correct = None
        attempt.feedback = "I couldn't match that response to one of the available choices. Please try another issued question."
    else:
        is_correct = selected.casefold() == attempt.expected_answer.casefold()
        attempt.is_correct = is_correct
        progress.evidence_attempts += 1
        progress.attempts = progress.evidence_attempts
        if is_correct:
            progress.correct_attempts += 1
            attempt.feedback = "Correct. " + _explanation(attempt.question_id)
        else:
            progress.incorrect_attempts += 1
            attempt.feedback = "Not quite. " + _explanation(attempt.question_id)
        progress.mastery_score = round(100 * progress.correct_attempts / progress.evidence_attempts, 1)
        progress.evidence_status = "assessed"
        progress.last_assessed_at = attempt.answered_at
        progress.updated_at = attempt.answered_at
    db.commit()
    db.refresh(progress)
    adaptation = recommend(progress.evidence_attempts, progress.correct_attempts, progress.incorrect_attempts,
                            _recent_outcomes(student.id, attempt.normalized_topic_key, db))
    return AnswerResponse(
        attempt_id=attempt.id, topic=attempt.topic, answer=answer, is_correct=attempt.is_correct,
        ambiguous=attempt.is_correct is None, feedback=attempt.feedback or "",
        mastery_score=progress.mastery_score if progress.evidence_attempts else None,
        evidence_attempts=progress.evidence_attempts, correct_attempts=progress.correct_attempts,
        incorrect_attempts=progress.incorrect_attempts, difficulty=adaptation.difficulty,
        strategy=adaptation.strategy, recommendation=adaptation.recommendation,
        reason=adaptation.reason, revision_recommended=adaptation.revision_recommended,
    )


def _explanation(question_id: str) -> str:
    from backend.app.services.assessment_bank import BANK
    for questions in BANK.values():
        for question in questions:
            if question.id == question_id:
                return question.explanation
    return "Review the worked example and try again."
