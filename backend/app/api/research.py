"""Authenticated, student-scoped educational research and safe task planning."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.app.api.auth import current_student
from backend.app.config import get_settings
from backend.app.db.models import ResearchAudit, ResearchSession, ResearchSourceRecord, ResearchTask, Student, utc_now
from backend.app.db.session import get_db
from backend.app.services.research import SearchUnavailable, get_search_provider, safe_public_url, generate_research_summary

router = APIRouter(prefix="/research", tags=["AI research"])
_recent_requests: dict[str, list[float]] = {}
_rate_lock = Lock()


class ResearchCreate(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    language: str = "mixed"

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Research question is too short")
        return value

    @field_validator("language")
    @classmethod
    def valid_language(cls, value: str) -> str:
        if value not in {"english", "telugu", "mixed"}:
            raise ValueError("Language must be english, telugu, or mixed")
        return value


class SourceOut(BaseModel):
    id: str
    title: str
    canonical_url: str
    publisher: str
    excerpt: str
    retrieved_at: datetime
    quality_note: str


class SessionOut(BaseModel):
    id: str
    question: str
    language: str
    status: str
    provider_mode: str | None
    summary: dict | None
    sources: list[SourceOut]
    created_at: datetime


class TaskCreate(BaseModel):
    action_type: str = Field(pattern="^(open_resource|compare_courses|study_checklist|draft_email|reminder_proposal)$")
    title: str = Field(min_length=3, max_length=200)
    payload: dict = Field(default_factory=dict, max_length=20)
    research_session_id: str | None = None

    @field_validator("payload")
    @classmethod
    def bounded_payload(cls, value: dict) -> dict:
        if len(json.dumps(value, ensure_ascii=False)) > 4000:
            raise ValueError("Task proposal payload must be at most 4000 characters")
        return value


class TaskOut(BaseModel):
    id: str
    action_type: str
    title: str
    payload: dict
    status: str
    approval_expires_at: datetime | None
    created_at: datetime
    executable: bool
    execution_notice: str


def _rate_limit(student_id: str) -> None:
    now = time.monotonic()
    limit = get_settings().research_requests_per_minute
    with _rate_lock:
        for key in list(_recent_requests):
            fresh = [stamp for stamp in _recent_requests[key] if now - stamp < 60]
            if fresh: _recent_requests[key] = fresh
            else: _recent_requests.pop(key, None)
        window = _recent_requests.get(student_id, [])
        if len(window) >= limit:
            raise HTTPException(status_code=429, detail="Research rate limit reached; try again shortly")
        _recent_requests[student_id] = [*window, now]


def _owned_session(session_id: str, student: Student, db: Session) -> ResearchSession:
    item = db.scalar(select(ResearchSession).options(selectinload(ResearchSession.sources)).where(ResearchSession.id == session_id, ResearchSession.student_id == student.id))
    if item is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return item


def _session_out(item: ResearchSession) -> SessionOut:
    citations = [SourceOut(id=source.id, title=source.title, canonical_url=source.canonical_url, publisher=source.publisher,
                           excerpt=source.excerpt, retrieved_at=source.retrieved_at,
                           quality_note=_quality_note(source.canonical_url)) for source in item.sources]
    return SessionOut(id=item.id, question=item.question, language=item.language, status=item.status,
                      provider_mode=item.provider_mode, summary=json.loads(item.summary_json) if item.summary_json else None,
                      sources=citations, created_at=item.created_at)


def _quality_note(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    if host.endswith((".edu", ".gov", ".gov.in", ".gov.uk")):
        return "Institutional domain; domain type only, content not independently verified."
    if host == "khanacademy.org" or host.endswith(".khanacademy.org") or host == "openstax.org" or host.endswith(".openstax.org"):
        return "Educational publisher domain; content not independently verified."
    return "Publisher not independently assessed; review the source directly."


def _task_out(item: ResearchTask) -> TaskOut:
    return TaskOut(id=item.id, action_type=item.action_type, title=item.title, payload=json.loads(item.payload_json),
                   status=item.status, approval_expires_at=item.approval_expires_at, created_at=item.created_at,
                   executable=item.executable,
                   execution_notice="External browser actions are unavailable; this approved plan was not executed.")


def _audit(db: Session, student_id: str, task_id: str | None, event: str) -> None:
    db.add(ResearchAudit(student_id=student_id, task_id=task_id, event=event))


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(payload: ResearchCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    item = ResearchSession(student_id=student.id, question=payload.question, language=payload.language, status="drafted")
    db.add(item); db.commit(); db.refresh(item)
    return _session_out(item)


@router.post("/sessions/{session_id}/run", response_model=SessionOut)
def run_research(session_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    _rate_limit(student.id)
    item = _owned_session(session_id, student, db)
    if item.status == "completed":
        return _session_out(item)
    item.status = "running"
    db.commit()
    provider, mode = get_search_provider()
    try:
        found = provider.search(item.question, limit=5)
    except SearchUnavailable as exc:
        item.status = "failed"; db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    existing = {source.canonical_url for source in item.sources}
    accepted = []
    for source in found:
        try:
            canonical_url = safe_public_url(source.url, resolve=mode == "live_brave")
        except ValueError:
            continue
        if canonical_url in existing:
            continue
        existing.add(canonical_url)
        accepted.append(source)
        db.add(ResearchSourceRecord(session_id=item.id, title=source.title[:300], canonical_url=canonical_url,
                                    publisher=source.publisher[:255], excerpt=source.excerpt[:1200], retrieved_at=source.retrieved_at))
    db.flush()
    db.refresh(item)
    item.provider_mode = mode
    item.summary_json = json.dumps(generate_research_summary(item.question, item.language, accepted, enable_ai=mode == "live_brave"), ensure_ascii=False)
    item.status = "completed"
    item.updated_at = utc_now()
    db.commit(); db.refresh(item)
    return _session_out(_owned_session(session_id, student, db))


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(student: Student = Depends(current_student), db: Session = Depends(get_db), limit: int = Query(30, ge=1, le=100)):
    items = db.scalars(select(ResearchSession).options(selectinload(ResearchSession.sources)).where(ResearchSession.student_id == student.id).order_by(ResearchSession.created_at.desc()).limit(limit)).all()
    return [_session_out(item) for item in items]


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return _session_out(_owned_session(session_id, student, db))


@router.get("/sessions/{session_id}/findings")
def get_findings(session_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    item = _owned_session(session_id, student, db)
    return {"session_id": item.id, "status": item.status,
            "summary": json.loads(item.summary_json) if item.summary_json else None,
            "citations": [SourceOut(id=source.id, title=source.title, canonical_url=source.canonical_url, publisher=source.publisher,
                                    excerpt=source.excerpt, retrieved_at=source.retrieved_at,
                                    quality_note=_quality_note(source.canonical_url)) for source in item.sources]}


@router.post("/sessions/{session_id}/study-plan")
def study_plan(session_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    item = _owned_session(session_id, student, db)
    if item.status != "completed":
        raise HTTPException(status_code=409, detail="Run research before creating a learning plan")
    activities = {
        "english": (["Read the first cited source and note three unfamiliar terms", "Explain one finding in your own words"], ["Compare the cited sources", "Write a short reflection and list open questions"]),
        "telugu": (["????? ???????? ????? ???? ????? ?????? ???????????", "?? ????????????? ?? ??????? ??????????"], ["???????? ??????? ????????", "????? ?????? ???? ???? ???? ????????? ?????? ??????"]),
        "mixed": (["Read the first cited source; ???? ????? ?????? ???????????", "Explain one finding ?? ???????"], ["Compare the cited sources; ???????? ????????????", "Write a short reflection; ???? ???? ????????? ???????????"]),
    }
    first_week, second_week = activities[item.language]
    return {"session_id": item.id, "language": item.language, "weeks": [
        {"week": 1, "focus": item.question[:160], "activities": first_week},
        {"week": 2, "focus": "Connect and review the evidence" if item.language == "english" else ("???????? ???????????? ????????????" if item.language == "telugu" else "Connect and review the evidence ? ???????? ????????????"), "activities": second_week},
    ]}


@router.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def propose_task(payload: TaskCreate, idempotency_key: str = Header(min_length=8, max_length=128, alias="Idempotency-Key"), student: Student = Depends(current_student), db: Session = Depends(get_db)):
    old = db.scalar(select(ResearchTask).where(ResearchTask.student_id == student.id, ResearchTask.idempotency_key == idempotency_key))
    serialized = json.dumps(payload.payload, ensure_ascii=False, sort_keys=True)
    if old:
        if old.action_type != payload.action_type or old.title != payload.title or old.payload_json != serialized:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different action")
        return _task_out(old)
    if payload.research_session_id:
        _owned_session(payload.research_session_id, student, db)
    task = ResearchTask(student_id=student.id, research_session_id=payload.research_session_id, action_type=payload.action_type,
                        title=payload.title.strip(), payload_json=serialized, idempotency_key=idempotency_key, status="drafted", executable=False)
    db.add(task)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(ResearchTask).where(ResearchTask.student_id == student.id, ResearchTask.idempotency_key == idempotency_key))
        if existing is None or existing.action_type != payload.action_type or existing.title != payload.title or existing.payload_json != serialized:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for a different action") from None
        return _task_out(existing)
    _audit(db, student.id, task.id, "drafted"); db.commit(); db.refresh(task)
    return _task_out(task)


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    items = db.scalars(select(ResearchTask).where(ResearchTask.student_id == student.id).order_by(ResearchTask.created_at.desc()).limit(100)).all()
    return [_task_out(item) for item in items]


@router.post("/tasks/{task_id}/request-approval", response_model=TaskOut)
def request_approval(task_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    task = db.scalar(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.student_id == student.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "drafted": raise HTTPException(status_code=409, detail="Only a drafted task can request approval")
    task.status = "awaiting_approval"; task.approval_expires_at = utc_now() + timedelta(minutes=15)
    _audit(db, student.id, task.id, "awaiting_approval"); db.commit(); db.refresh(task)
    return _task_out(task)


@router.post("/tasks/{task_id}/approve", response_model=TaskOut)
def approve_task(task_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    task = db.scalar(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.student_id == student.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "awaiting_approval": raise HTTPException(status_code=409, detail="This task is not awaiting approval")
    expires_at = task.approval_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not expires_at or expires_at < utc_now():
        task.status = "failed"; _audit(db, student.id, task.id, "approval_expired"); db.commit()
        raise HTTPException(status_code=410, detail="Approval expired; prepare a new task proposal")
    task.status = "approved"; task.executable = False
    _audit(db, student.id, task.id, "approved"); db.commit(); db.refresh(task)
    return _task_out(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
def cancel_task(task_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    task = db.scalar(select(ResearchTask).where(ResearchTask.id == task_id, ResearchTask.student_id == student.id))
    if task is None: raise HTTPException(status_code=404, detail="Task not found")
    if task.status in {"completed", "failed", "cancelled"}: raise HTTPException(status_code=409, detail="Task can no longer be cancelled")
    task.status = "cancelled"; task.executable = False
    _audit(db, student.id, task.id, "cancelled"); db.commit(); db.refresh(task)
    return _task_out(task)


@router.get("/audit")
def audit_history(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(ResearchAudit).where(ResearchAudit.student_id == student.id).order_by(ResearchAudit.created_at.desc()).limit(100)).all()
    return [{"task_id": row.task_id, "event": row.event, "created_at": row.created_at} for row in rows]
