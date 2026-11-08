"""Student-private document learning studio APIs."""
from __future__ import annotations

import json
import re
import time
from collections import deque
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.documents import get_embedding_provider
from backend.app.db.models import Document, DocumentIndexState, Student
from backend.app.db.session import get_db
from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider
from backend.app.services.rag_tutor import (
    DEFAULT_MIN_SCORE, MAX_PASSAGES, Citation, GeneratedAnswer, RetrievalRequest,
    VectorPassageRetriever, attribute_answer, build_rag_generation_request,
)
from backend.app.services.tutor import generate_tutor_reply

router = APIRouter(prefix="/knowledge", tags=["knowledge studio"])
LANGUAGES = {"english", "telugu", "mixed"}
LEARNING_MODES = {"summary", "concepts", "flashcards", "practice", "quiz"}
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_REQUESTS = 30
_RATE_LIMIT: dict[str, deque[float]] = {}
_RATE_LIMIT_LOCK = Lock()


def _enforce_rate_limit(student_id: str) -> None:
    now = time.monotonic()
    with _RATE_LIMIT_LOCK:
        events = _RATE_LIMIT.setdefault(student_id, deque())
        while events and now - events[0] >= _RATE_LIMIT_WINDOW_SECONDS:
            events.popleft()
        if len(events) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(status_code=429, detail="Knowledge Studio is busy. Wait a minute and try again.")
        events.append(now)
        if len(_RATE_LIMIT) > 5000:
            for owner, queue in list(_RATE_LIMIT.items()):
                while queue and now - queue[0] >= _RATE_LIMIT_WINDOW_SECONDS:
                    queue.popleft()
                if not queue:
                    _RATE_LIMIT.pop(owner, None)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1200)


class AskRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=10)
    question: str = Field(min_length=1, max_length=1200)
    language: str = "mixed"
    history: list[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        value = value.casefold()
        if value not in LANGUAGES:
            raise ValueError("Language must be english, telugu, or mixed")
        return value

    @model_validator(mode="after")
    def unique_documents(self):
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("Select each document only once")
        return self


class LearningRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=10)
    mode: str
    topic: str = Field(default="", max_length=200)
    language: str = "mixed"

    @field_validator("mode")
    @classmethod
    def valid_mode(cls, value: str) -> str:
        value = value.casefold()
        if value not in LEARNING_MODES:
            raise ValueError("Unsupported learning mode")
        return value

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        value = value.casefold()
        if value not in LANGUAGES:
            raise ValueError("Language must be english, telugu, or mixed")
        return value

    @model_validator(mode="after")
    def unique_documents(self):
        if len(set(self.document_ids)) != len(self.document_ids):
            raise ValueError("Select each document only once")
        return self


class CitationResponse(BaseModel):
    citation_id: str
    document_id: str
    document_title: str
    page_number: int


class QuizQuestion(BaseModel):
    question: str = Field(min_length=4, max_length=500)
    choices: list[str] = Field(min_length=2, max_length=5)
    correct_index: int = Field(ge=0, le=4)
    explanation: str = Field(min_length=4, max_length=1000)
    citation_ids: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def valid_answer_index(self):
        if self.correct_index >= len(self.choices) or len(set(self.choices)) != len(self.choices):
            raise ValueError("Quiz answer key is invalid")
        return self


def _owned_ready_documents(db: Session, student_id: str, document_ids: list[str]) -> None:
    owned = set(db.scalars(select(Document.id).where(
        Document.id.in_(document_ids), Document.student_id == student_id,
        Document.processing_status == "processed",
    )).all())
    ready = set(db.scalars(select(DocumentIndexState.document_id).where(
        DocumentIndexState.document_id.in_(document_ids),
        DocumentIndexState.student_id == student_id,
        DocumentIndexState.status == "ready",
        DocumentIndexState.active_generation_id.is_not(None),
    )).all())
    if len(owned) != len(document_ids):
        raise HTTPException(status_code=404, detail="One or more selected documents were not found")
    if ready != set(document_ids):
        raise HTTPException(status_code=409, detail="Index each selected text document before using the studio")


def _retrieve(db: Session, student_id: str, document_ids: list[str], query: str, provider: GeminiEmbeddingProvider):
    request = RetrievalRequest(
        student_id=student_id, query=query, topic="Document study", limit=MAX_PASSAGES,
        document_ids=tuple(document_ids),
    )
    result = VectorPassageRetriever(db, provider).retrieve(request)
    return tuple(p for p in result.passages if p.score >= DEFAULT_MIN_SCORE and p.text.strip())[:MAX_PASSAGES]


def _generate_from_sources(*, passages, instruction: str, question: str, language: str, history=None) -> tuple[str, tuple[Citation, ...], str]:
    base = build_rag_generation_request(
        question=question, topic="Selected study documents", language=language,
        level="student", passages=passages,
    )
    prompt = json.loads(base.user_prompt)
    if history:
        # Conversation is bounded context for resolving follow-ups; it is never source evidence.
        prompt["recent_conversation_context_untrusted"] = [turn.model_dump() for turn in history]
    prompt["requested_learning_task"] = instruction
    generated_text = generate_tutor_reply(base.system_instruction, [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}])
    citations = tuple(Citation(f"S{index}", p.document_id, p.document_title, p.page_number) for index, p in enumerate(passages, 1))
    answer, cited = attribute_answer(GeneratedAnswer(generated_text), citations)
    return answer, cited, generated_text


@router.post("/ask")
def ask_documents(
    payload: AskRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    provider: GeminiEmbeddingProvider = Depends(get_embedding_provider),
):
    _enforce_rate_limit(student.id)
    _owned_ready_documents(db, student.id, payload.document_ids)
    try:
        passages = _retrieve(db, student.id, payload.document_ids, payload.question, provider)
        answer, citations, _raw = _generate_from_sources(
            passages=passages,
            instruction="Answer the student's question using only the retrieved sources. If they do not support an answer, clearly say the selected documents do not contain enough evidence. Use any recent conversation only to interpret a follow-up. Cite each supported claim with its supplied [S#] marker.",
            question=payload.question, language=payload.language, history=payload.history,
        )
    except EmbeddingError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Document search is unavailable. Please retry.") from None
    return {
        "answer": answer,
        "citations": [CitationResponse(**citation.__dict__) for citation in citations],
        "grounded": bool(citations),
        "retrieval_used": bool(passages),
        "uncertainty": "No sufficiently relevant source passages were found." if not passages else None,
    }


@router.post("/learning")
def generate_learning_material(
    payload: LearningRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    provider: GeminiEmbeddingProvider = Depends(get_embedding_provider),
):
    _enforce_rate_limit(student.id)
    _owned_ready_documents(db, student.id, payload.document_ids)
    topic = payload.topic.strip() or "the main ideas"
    task = {
        "summary": "Write a concise section-aware summary of the selected documents. Mark uncertain or missing source detail.",
        "concepts": "Extract the key concepts and explain each briefly using only retrieved evidence.",
        "flashcards": "Create 5 study flashcards as Front: ... / Back: ... pairs from the retrieved evidence.",
        "practice": "Create 5 document-grounded practice questions followed by short model answers and explanations.",
        "quiz": "Return ONLY valid JSON: an object with a questions array of 5 multiple-choice questions. Each item must contain question, choices (4 distinct strings), correct_index (0-based integer), explanation, citation_ids (array of supplied IDs such as S1). Every answer and explanation must be supported by the retrieved passages. Include [S#] markers in explanations and never invent source IDs.",
    }[payload.mode]
    try:
        passages = _retrieve(db, student.id, payload.document_ids, topic if payload.mode != "summary" else "main ideas, chapter sections and key concepts", provider)
        if not passages:
            return {"mode": payload.mode, "content": "The selected documents do not provide enough indexed evidence to generate this material.", "questions": [], "citations": [], "grounded": False}
        answer, citations, raw_answer = _generate_from_sources(
            passages=passages,
            instruction=f"{task} Focus on topic: {topic}. Do not fill gaps with outside facts. Cite each generated item with available [S#] markers.",
            question=f"Generate {payload.mode} from selected study documents about {topic}.",
            language=payload.language,
        )
    except EmbeddingError as exc:
        raise HTTPException(status_code=exc.status_code, detail="Document search is unavailable. Please retry.") from None

    if payload.mode != "quiz":
        return {"mode": payload.mode, "content": answer, "questions": [], "citations": [CitationResponse(**c.__dict__) for c in citations], "grounded": bool(citations)}
    # Quiz JSON is schema-checked before it reaches the browser; citations are restricted to retrieved IDs.
    try:
        parsed = json.loads(raw_answer)
        raw_questions = parsed["questions"] if isinstance(parsed, dict) else None
        if not isinstance(raw_questions, list) or not 1 <= len(raw_questions) <= 5:
            raise ValueError("invalid question count")
        questions = [QuizQuestion.model_validate(item) for item in raw_questions]
        available_sources = {f"S{index}": Citation(f"S{index}", p.document_id, p.document_title, p.page_number) for index, p in enumerate(passages, 1)}
        available_ids = set(available_sources)
        invalid_marker = re.compile(r"\[(S\d+)\]")
        if any(not set(q.citation_ids).issubset(available_ids) for q in questions):
            raise ValueError("unknown citation id")
        if any(not q.citation_ids for q in questions):
            raise ValueError("quiz question has no page citation")
        if any(not set(invalid_marker.findall("\n".join([q.question, *q.choices, q.explanation]))).issubset(available_ids) for q in questions):
            raise ValueError("unknown citation marker")
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=502, detail="The learning provider returned an invalid quiz. Please retry.") from None
    return {
        "mode": "quiz", "content": "Answer each question, then check your results.",
        "questions": [question.model_dump() for question in questions],
        "citations": [CitationResponse(**available_sources[citation_id].__dict__) for citation_id in sorted({citation_id for q in questions for citation_id in q.citation_ids})],
        "grounded": True,
    }
