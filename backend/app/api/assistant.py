"""Private INT17 assistant preferences, deadlines, approvals and provider status."""
from __future__ import annotations

import hashlib
import base64
import json
import re
import secrets
from email.utils import parseaddr
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import (AssistantAccount, AssistantAuditEvent, AssistantCallAttempt, AssistantCalendarEvent,
    AssistantDeadline, AssistantDeadlineCandidate, AssistantDraft, AssistantEmailMessage, AssistantJob,
    AssistantOAuthState, AssistantSettings, Student, new_id)
from backend.app.db.session import get_db
from backend.app.config import get_settings
from backend.app.services.assistant_providers import (ProviderFailure, ProviderUnavailable, decrypt_token,
    encrypt_token, google_authorization_url, google_exchange_code, google_ready, twilio_live_ready,
    twilio_verify_start, twilio_verify_check, verify_twilio_signature, twilio_create_call)
from backend.app.services.assistant_google import (sync_gmail, list_calendar_events, create_calendar_event,
    generate_reply, send_gmail_draft, oauth_user_email)
from backend.app.services.gnani_voice import VoiceProviderNotConfigured, create_prisma_client, create_timbre_adapter
from pocs.poc01_prisma_stt.prisma_stt import STTError, validate_audio
from pocs.poc06_bilingual_voice.stt_adapter import PrismaTranscriptionAdapter, STTStageError
from pocs.poc06_bilingual_voice.tts_adapter import TTSStageError
from pocs.poc04_adaptive_teaching.models import Language

router = APIRouter(prefix="/assistant", tags=["personal assistant"])


def _json(value, fallback):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _audit(db: Session, owner: str, action: str, target_type: str, target_id: str | None, outcome: str, details=None):
    db.add(AssistantAuditEvent(student_id=owner, action=action, target_type=target_type, target_id=target_id,
                               outcome=outcome, details_json=json.dumps(details or {}, separators=(",", ":"))))


class SettingsUpdate(BaseModel):
    modes: list[str] | None = Field(default=None, min_length=1, max_length=2)
    timezone: str | None = Field(default=None, max_length=80)
    preferred_language: str | None = Field(default=None, pattern="^(en|te|mixed)$")
    reminder_phone: str | None = Field(default=None, max_length=32)
    call_consent: bool | None = None
    reminder_lead_minutes: list[int] | None = Field(default=None, max_length=8)
    quiet_start: str | None = None
    quiet_end: str | None = None
    email_policy: str | None = Field(default=None, pattern="^(draft_only|disabled|auto_rules)$")
    notifications: dict[str, bool] | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    paused: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, TypeError):
            raise ValueError("Use a valid IANA timezone")
        return value

    @field_validator("modes")
    @classmethod
    def valid_modes(cls, value):
        if value is not None and (len(set(value)) != len(value) or not set(value) <= {"student", "personal"}):
            raise ValueError("Modes must be student and/or personal")
        return value

    @field_validator("reminder_phone")
    @classmethod
    def phone_format(cls, value):
        if value is not None and value and not re.fullmatch(r"\+[1-9]\d{7,14}", value):
            raise ValueError("Phone must use E.164 format; verification is still required before calls")
        return value or None

    @field_validator("reminder_lead_minutes")
    @classmethod
    def leads_valid(cls, value):
        if value is not None and any(item < 0 or item > 525600 for item in value):
            raise ValueError("Reminder lead times must be between 0 and 525600 minutes")
        return sorted(set(value or []), reverse=True)

    @field_validator("notifications")
    @classmethod
    def valid_notifications(cls, value):
        if value is not None and not set(value) <= {"email", "call"}:
            raise ValueError("Only email and call notification preferences are supported")
        return value

    @model_validator(mode="after")
    def quiet_pair(self):
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError("Quiet hours need both a start and end")
        return self


class SettingsView(BaseModel):
    modes: list[str]
    timezone: str
    preferred_language: str
    reminder_phone: str | None
    phone_verified: bool
    call_consent: bool
    reminder_lead_minutes: list[int]
    quiet_start: str | None
    quiet_end: str | None
    enabled_integrations: list[str]
    email_policy: str
    notifications: dict
    retention_days: int
    paused: bool


def _view(row: AssistantSettings) -> SettingsView:
    return SettingsView(modes=_json(row.modes_json, ["student"]), timezone=row.timezone_name,
                        preferred_language=row.preferred_language, reminder_phone=row.reminder_phone,
                        phone_verified=row.phone_verified, call_consent=bool(row.call_consent_at),
                        reminder_lead_minutes=_json(row.reminder_lead_minutes_json, [1440, 60]),
                        quiet_start=row.quiet_start, quiet_end=row.quiet_end,
                        enabled_integrations=_json(row.enabled_integrations_json, []), email_policy=row.email_policy,
                        notifications=_json(row.notifications_json, {}), retention_days=row.retention_days, paused=row.paused)


def _settings(db: Session, owner: str) -> AssistantSettings:
    row = db.get(AssistantSettings, owner)
    if row is None:
        row = AssistantSettings(student_id=owner)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/settings", response_model=SettingsView)
def get_assistant_settings(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return _view(_settings(db, student.id))


@router.patch("/settings", response_model=SettingsView)
def update_assistant_settings(payload: SettingsUpdate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _settings(db, student.id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("email_policy") == "auto_rules":
        raise HTTPException(409, "Automatic replies are unavailable until explicit narrow rules and an authorized Gmail provider are configured")
    if "modes" in data: row.modes_json = json.dumps(data.pop("modes"))
    if "timezone" in data: row.timezone_name = data.pop("timezone")
    if "reminder_lead_minutes" in data: row.reminder_lead_minutes_json = json.dumps(data.pop("reminder_lead_minutes"))
    if "notifications" in data:
        preferences = _json(row.notifications_json, {"email": True, "call": False})
        preferences.update(data.pop("notifications"))
        row.notifications_json = json.dumps(preferences, separators=(",", ":"))
    if "call_consent" in data:
        consent = data.pop("call_consent")
        if consent and not (row.reminder_phone and row.phone_verified):
            raise HTTPException(409, "Verify a phone number before enabling call consent")
        row.call_consent_at = datetime.now(timezone.utc) if consent else None
    if "reminder_phone" in data:
        phone = data.pop("reminder_phone")
        if phone != row.reminder_phone:
            row.phone_verified = False
            row.call_consent_at = None
        row.reminder_phone = phone
    for key, value in data.items():
        if key in {"quiet_start", "quiet_end"} and value is not None and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
            raise HTTPException(422, "Quiet hours must use HH:MM")
        setattr(row, key, value)
    _audit(db, student.id, "settings.updated", "settings", student.id, "saved", {"changed": sorted(payload.model_fields_set)})
    db.commit(); db.refresh(row)
    return _view(row)


class DeadlineCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime
    timezone: str | None = Field(default=None, max_length=80)
    priority: str = Field(default="normal", pattern="^(low|normal|high|urgent)$")
    category: str = Field(default="personal", max_length=40)

    @field_validator("title", "description")
    @classmethod
    def trim_text(cls, value):
        if value is None: return value
        value = value.strip()
        if not value: raise ValueError("Cannot be blank")
        return value

    @field_validator("due_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Deadline must include an explicit timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        if value:
            try: ZoneInfo(value)
            except ZoneInfoNotFoundError: raise ValueError("Use a valid IANA timezone")
        return value


class DeadlineView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str | None
    due_at: datetime
    timezone_name: str
    priority: str
    category: str
    status: str
    source: str


class DeadlineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=80)
    priority: str | None = Field(default=None, pattern="^(low|normal|high|urgent)$")
    category: str | None = Field(default=None, max_length=40)

    @field_validator("due_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Deadline must include an explicit timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        if value:
            try: ZoneInfo(value)
            except ZoneInfoNotFoundError: raise ValueError("Use a valid IANA timezone")
        return value

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        return self


def _deadline(row):
    return DeadlineView(id=row.id, title=row.title, description=row.description, due_at=row.due_at,
                        timezone_name=row.timezone_name, priority=row.priority, category=row.category,
                        status=row.status, source=row.source)


def _owned_deadline(db: Session, owner: str, deadline_id: str):
    row = db.scalar(select(AssistantDeadline).where(AssistantDeadline.id == deadline_id, AssistantDeadline.student_id == owner))
    if row is None: raise HTTPException(404, "Deadline not found")
    return row


@router.post("/deadlines", response_model=DeadlineView, status_code=status.HTTP_201_CREATED)
def create_deadline(payload: DeadlineCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    settings = _settings(db, student.id)
    zone = payload.timezone or settings.timezone_name
    instant = payload.due_at.astimezone(timezone.utc)
    key = hashlib.sha256(f"{student.id}|{payload.title.casefold()}|{instant.isoformat()}".encode()).hexdigest()
    existing = db.scalar(select(AssistantDeadline).where(AssistantDeadline.student_id == student.id, AssistantDeadline.dedupe_key == key))
    if existing: return _deadline(existing)
    row = AssistantDeadline(id=new_id(), student_id=student.id, title=payload.title, description=payload.description,
                            due_at=instant, timezone_name=zone, priority=payload.priority, category=payload.category,
                            status="upcoming", source="manual", dedupe_key=key, confirmed_at=datetime.now(timezone.utc))
    db.add(row); db.flush()
    for lead in _json(settings.reminder_lead_minutes_json, [1440, 60]):
        run_at = instant - timedelta(minutes=lead)
        if run_at > datetime.now(timezone.utc):
            db.add(AssistantJob(student_id=student.id, deadline_id=row.id, kind="reminder", status="queued", run_at=run_at,
                                idempotency_key=f"deadline:{row.id}:lead:{lead}", attempts=0, max_attempts=5))
    _audit(db, student.id, "deadline.created", "deadline", row.id, "saved", {"source": "manual"})
    try: db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(AssistantDeadline).where(AssistantDeadline.student_id == student.id, AssistantDeadline.dedupe_key == key))
        if existing: return _deadline(existing)
        raise
    db.refresh(row)
    return _deadline(row)


@router.get("/deadlines", response_model=list[DeadlineView])
def list_deadlines(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return [_deadline(r) for r in db.scalars(select(AssistantDeadline).where(AssistantDeadline.student_id == student.id).order_by(AssistantDeadline.due_at).limit(200)).all()]


@router.patch("/deadlines/{deadline_id}", response_model=DeadlineView)
def update_deadline(deadline_id: str, payload: DeadlineUpdate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _owned_deadline(db, student.id, deadline_id)
    if row.status != "upcoming": raise HTTPException(409, "Only upcoming deadlines can be edited")
    data = payload.model_dump(exclude_unset=True)
    if "due_at" in data and data["due_at"] is not None:
        row.due_at = data["due_at"].astimezone(timezone.utc)
    if "timezone" in data and data["timezone"] is not None: row.timezone_name = data["timezone"]
    for field in ("title", "description", "priority", "category"):
        if field in data and data[field] is not None: setattr(row, field, data[field])
    if "due_at" in data:
        db.query(AssistantJob).filter(AssistantJob.student_id == student.id, AssistantJob.deadline_id == row.id,
                                      AssistantJob.status.in_(["queued", "retry"])).update({"status": "canceled"}, synchronize_session=False)
        settings = _settings(db, student.id)
        for lead in _json(settings.reminder_lead_minutes_json, [1440, 60]):
            run_at = row.due_at - timedelta(minutes=lead)
            if run_at > datetime.now(timezone.utc):
                db.add(AssistantJob(student_id=student.id, deadline_id=row.id, kind="reminder", status="queued", run_at=run_at,
                                    idempotency_key=f"deadline:{row.id}:edit:{row.due_at.isoformat()}:lead:{lead}", attempts=0, max_attempts=5))
    _audit(db, student.id, "deadline.updated", "deadline", row.id, "saved", {"changed": sorted(data)})
    db.commit(); db.refresh(row)
    return _deadline(row)


@router.post("/deadlines/{deadline_id}/{action}", response_model=DeadlineView)
def deadline_action(deadline_id: str, action: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _owned_deadline(db, student.id, deadline_id)
    if action not in {"complete", "cancel"}: raise HTTPException(404, "Action not found")
    row.status = "completed" if action == "complete" else "canceled"
    db.query(AssistantJob).filter(AssistantJob.student_id == student.id, AssistantJob.deadline_id == row.id, AssistantJob.status.in_(["queued", "retry"])).update({"status": "canceled"}, synchronize_session=False)
    _audit(db, student.id, f"deadline.{action}d", "deadline", row.id, "saved")
    db.commit(); db.refresh(row)
    return _deadline(row)


class DraftCreate(BaseModel):
    thread_ref: str = Field(min_length=1, max_length=255)
    recipient: EmailStr
    subject: str = Field(max_length=500)
    body: str = Field(min_length=1, max_length=20000)
    risk_category: str = Field(default="low", pattern="^(low|financial|legal|sensitive|employment|medical|security|uncertain|attachment|other)$")


class DraftView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    thread_ref: str
    recipient: str
    subject: str
    body: str
    risk_category: str
    status: str
    approved_at: datetime | None


def _owned_draft(db, owner, draft_id):
    row = db.scalar(select(AssistantDraft).where(AssistantDraft.id == draft_id, AssistantDraft.student_id == owner))
    if row is None: raise HTTPException(404, "Draft not found")
    return row


@router.get("/drafts", response_model=list[DraftView])
def list_drafts(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return db.scalars(select(AssistantDraft).where(AssistantDraft.student_id == student.id).order_by(AssistantDraft.created_at.desc()).limit(100)).all()


@router.post("/drafts", response_model=DraftView, status_code=201)
def create_draft(payload: DraftCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = AssistantDraft(student_id=student.id, **payload.model_dump())
    db.add(row); db.flush(); _audit(db, student.id, "email.draft.created", "draft", row.id, "draft_only")
    db.commit(); db.refresh(row)
    return row


@router.post("/drafts/{draft_id}/approve", response_model=DraftView)
def approve_draft(draft_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _owned_draft(db, student.id, draft_id)
    if row.status not in {"draft", "rejected"}: raise HTTPException(409, "Draft cannot be approved in its current state")
    row.status = "approved"; row.approved_at = datetime.now(timezone.utc)
    _audit(db, student.id, "email.draft.approved", "draft", row.id, "approved")
    db.commit(); db.refresh(row)
    return row


@router.post("/drafts/{draft_id}/reject", response_model=DraftView)
def reject_draft(draft_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _owned_draft(db, student.id, draft_id)
    if row.status in {"sent", "rejected"}: raise HTTPException(409, "Draft cannot be rejected in its current state")
    row.status = "rejected"; _audit(db, student.id, "email.draft.rejected", "draft", row.id, "rejected")
    db.commit(); db.refresh(row)
    return row


@router.post("/drafts/{draft_id}/send")
def send_draft(draft_id: str, idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=128),
               student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = db.scalar(select(AssistantDraft).where(AssistantDraft.id == draft_id,
        AssistantDraft.student_id == student.id).with_for_update())
    if row is None: raise HTTPException(404, "Draft not found")
    if row.status == "sent": return {"id": row.id, "status": "sent", "provider_message_id": row.provider_message_id}
    if row.status in {"sending", "send_uncertain"}: raise HTTPException(409, "Send outcome is being verified; do not retry this message")
    if row.status != "approved" or row.approved_at is None: raise HTTPException(409, "Explicit approval is required")
    if not google_ready(): raise HTTPException(503, "Live Gmail sending is disabled or not configured; the approved draft remains unsent")
    account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == student.id,
        AssistantAccount.provider == "gmail", AssistantAccount.status == "connected").with_for_update())
    if account is None: raise HTTPException(409, "Connect Gmail before sending")
    granted = set(_json(account.granted_scopes, []))
    if "https://www.googleapis.com/auth/gmail.send" not in granted:
        raise HTTPException(403, "Gmail send permission was not granted")
    collision = db.scalar(select(AssistantDraft.id).where(AssistantDraft.student_id == student.id,
        AssistantDraft.idempotency_key == idempotency_key, AssistantDraft.id != row.id))
    if collision: raise HTTPException(409, "Idempotency key was already used for another draft")
    row.status = "sending"; row.idempotency_key = idempotency_key; row.failure_code = None
    _audit(db, student.id, "email.send.started", "draft", row.id, "approved_send")
    db.commit()  # Persist the single-send lock before making the non-idempotent Gmail request.
    try:
        result = send_gmail_draft(account, recipient=row.recipient, subject=row.subject, body=row.body,
            thread_ref=row.thread_ref, rfc_message_id=row.rfc_message_id, references=row.references_header)
    except (ProviderFailure, ProviderUnavailable) as exc:
        code = exc.code if isinstance(exc, ProviderFailure) else "google_provider_unavailable"
        row = _owned_draft(db, student.id, draft_id)
        row.status = "send_uncertain" if code == "email_send_outcome_uncertain" else "send_failed"
        row.failure_code = code
        if code == "google_reauthorization_required": account.status = "reauthorization_required"
        _audit(db, student.id, "email.send.failed", "draft", row.id, row.status, {"code": code})
        db.commit()
        raise HTTPException(502, "Gmail send did not complete; inspect the mailbox before retrying")
    row = _owned_draft(db, student.id, draft_id)
    row.status = "sent"; row.provider_message_id = result["message_id"]; row.failure_code = None
    _audit(db, student.id, "email.sent", "draft", row.id, "provider_confirmed", {"provider_message_id": result["message_id"]})
    db.commit()
    return {"id": row.id, "status": "sent", "provider_message_id": row.provider_message_id}


@router.get("/integrations")
def integrations(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(AssistantAccount).where(AssistantAccount.student_id == student.id)).all()
    current = {row.provider: row for row in rows}
    cfg = get_settings()
    return [{"provider": provider, "status": current[provider].status if provider in current else "disconnected",
             "account_email": current[provider].account_email if provider in current else None,
             "available": google_ready(cfg), "message": "Connected" if current.get(provider) and current[provider].status == "connected" else ("Ready to connect" if google_ready(cfg) else "OAuth is disabled or not configured")}
            for provider in ("gmail", "calendar")]


@router.post("/integrations/{provider}/connect")
def connect_google(provider: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if provider not in {"gmail", "calendar"}: raise HTTPException(404, "Integration not found")
    if not google_ready(): raise HTTPException(503, "Google OAuth is disabled or not configured")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    scopes = google_authorization_url(provider, state, challenge)
    db.add(AssistantOAuthState(student_id=student.id, provider=provider,
        state_hash=hashlib.sha256(state.encode()).hexdigest(), code_verifier=verifier,
        requested_scopes=json.dumps(list(__import__("backend.app.services.assistant_providers", fromlist=["google_scopes"]).google_scopes(provider))),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    _audit(db, student.id, "oauth.started", provider, None, "consent_requested")
    db.commit()
    return {"authorization_url": scopes, "expires_in_seconds": 600}


@router.get("/integrations/{provider}/callback")
def google_oauth_callback(provider: str, state: str, code: str | None = None, error: str | None = None,
                          db: Session = Depends(get_db)):
    if provider not in {"gmail", "calendar"}: raise HTTPException(404, "Integration not found")
    state_hash = hashlib.sha256(state.encode()).hexdigest()
    oauth_state = db.scalar(select(AssistantOAuthState).where(AssistantOAuthState.state_hash == state_hash,
        AssistantOAuthState.provider == provider).with_for_update())
    now = datetime.now(timezone.utc)
    expires = oauth_state.expires_at.replace(tzinfo=timezone.utc) if oauth_state and oauth_state.expires_at.tzinfo is None else (oauth_state.expires_at if oauth_state else None)
    if oauth_state is None or oauth_state.consumed_at is not None or expires is None or expires <= now:
        raise HTTPException(400, "OAuth state is invalid, expired, or already used")
    oauth_state.consumed_at = now
    if error or not code:
        _audit(db, oauth_state.student_id, "oauth.denied", provider, None, "consent_denied")
        db.commit()
        raise HTTPException(400, "Google authorization was not granted")
    db.commit()  # Consume before exchanging: a callback can never replay the authorization code.
    try:
        token_data = google_exchange_code(code, oauth_state.code_verifier)
        access = str(token_data["access_token"])
        email = oauth_user_email(access)
        granted = set(str(token_data.get("scope", "")).split())
        expected = set(_json(oauth_state.requested_scopes, []))
        if expected and not expected <= granted:
            raise ProviderFailure("oauth_scopes_incomplete")
        cfg = get_settings()
        account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == oauth_state.student_id,
                                                           AssistantAccount.provider == provider))
        if account is None:
            account = AssistantAccount(student_id=oauth_state.student_id, provider=provider)
            db.add(account)
        account.status = "connected"; account.account_email = email
        account.access_token_enc = encrypt_token(access, cfg)
        refresh = token_data.get("refresh_token")
        if refresh: account.refresh_token_enc = encrypt_token(str(refresh), cfg)
        account.token_expires_at = now + timedelta(seconds=int(token_data.get("expires_in", 3600)))
        account.granted_scopes = json.dumps(sorted(granted))
        account.last_error = None
        _audit(db, oauth_state.student_id, "oauth.connected", provider, account.id, "connected", {"scope_count": len(granted)})
        if provider in {"gmail", "calendar"}:
            first_sync = now + timedelta(seconds=1)
            job_kind = "gmail_sync" if provider == "gmail" else "calendar_sync"
            db.add(AssistantJob(student_id=oauth_state.student_id, kind=job_kind, status="queued", run_at=first_sync,
                idempotency_key=f"{job_kind}:{account.id}:{int(first_sync.timestamp() // 900)}", attempts=0, max_attempts=5))
        db.commit()
    except (ProviderFailure, ProviderUnavailable, ValueError, TypeError):
        db.rollback()
        account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == oauth_state.student_id,
                                                           AssistantAccount.provider == provider))
        if account:
            account.status = "error"; account.last_error = "oauth_exchange_failed"; db.commit()
        raise HTTPException(502, "Google authorization could not be completed; reconnect and try again")
    cfg = get_settings()
    return RedirectResponse((cfg.assistant_public_base_url.rstrip("/") or "") + "/assistant?connected=" + provider, status_code=303)


@router.delete("/integrations/{provider}")
def disconnect_google(provider: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if provider not in {"gmail", "calendar"}: raise HTTPException(404, "Integration not found")
    account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == student.id,
                                                        AssistantAccount.provider == provider))
    if account is None: return {"provider": provider, "status": "disconnected", "revoked": True}
    token = None
    try:
        if account.refresh_token_enc: token = decrypt_token(account.refresh_token_enc)
        elif account.access_token_enc: token = decrypt_token(account.access_token_enc)
        if token:
            from backend.app.services.assistant_providers import google_revoke_token
            google_revoke_token(token)
        revoked = True
    except (ProviderFailure, ProviderUnavailable):
        revoked = False
    account.status = "disconnected"; account.access_token_enc = None; account.refresh_token_enc = None
    account.token_expires_at = None; account.granted_scopes = None; account.cursor = None; account.account_email = None
    account.last_error = None if revoked else "revocation_pending"
    _audit(db, student.id, "oauth.disconnected", provider, account.id, "revoked" if revoked else "local_tokens_cleared")
    db.commit()
    return {"provider": provider, "status": "disconnected", "revoked": revoked}


@router.post("/integrations/gmail/sync")
def gmail_sync(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == student.id,
                                                        AssistantAccount.provider == "gmail", AssistantAccount.status == "connected"))
    if account is None: raise HTTPException(409, "Connect Gmail before synchronizing")
    try: result = sync_gmail(db, student.id, account)
    except ProviderFailure as exc:
        account.last_error = exc.code
        if exc.code == "google_reauthorization_required": account.status = "reauthorization_required"
        _audit(db, student.id, "gmail.sync.failed", "integration", account.id, exc.code)
        db.commit()
        raise HTTPException(502, "Gmail synchronization failed; check the integration status")
    except ProviderUnavailable as exc:
        raise HTTPException(503, str(exc))
    _audit(db, student.id, "gmail.sync.completed", "integration", account.id, "synced", {"processed": result["processed"]})
    db.commit()
    return {"status": "synced", **result}


@router.get("/emails")
def list_synced_emails(student: Student = Depends(current_student), db: Session = Depends(get_db), limit: int = 50):
    limit = max(1, min(limit, 100))
    rows = db.scalars(select(AssistantEmailMessage).where(AssistantEmailMessage.student_id == student.id)
                      .order_by(AssistantEmailMessage.internal_date.desc()).limit(limit)).all()
    return [{"id": row.id, "message_ref": row.message_ref, "thread_ref": row.thread_ref, "sender": row.sender,
             "subject": row.subject, "snippet": row.snippet, "category": row.category,
             "needs_reply": row.needs_reply, "internal_date": row.internal_date} for row in rows]


@router.get("/deadline-candidates")
def list_deadline_candidates(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(AssistantDeadlineCandidate).where(AssistantDeadlineCandidate.student_id == student.id,
        AssistantDeadlineCandidate.status == "needs_confirmation").order_by(AssistantDeadlineCandidate.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "source_ref": row.source_ref, "title": row.title, "date_phrase": row.date_phrase,
             "due_at": row.due_at, "status": row.status} for row in rows]


class CandidateConfirm(BaseModel):
    due_at: datetime
    timezone: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=200)

    @field_validator("due_at")
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError("Confirm with an explicit timezone")
        return value


@router.post("/deadline-candidates/{candidate_id}/confirm")
def confirm_deadline_candidate(candidate_id: str, payload: CandidateConfirm, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    candidate = db.scalar(select(AssistantDeadlineCandidate).where(AssistantDeadlineCandidate.id == candidate_id,
        AssistantDeadlineCandidate.student_id == student.id).with_for_update())
    if candidate is None: raise HTTPException(404, "Deadline candidate not found")
    if candidate.status != "needs_confirmation": raise HTTPException(409, "Deadline candidate was already reviewed")
    title = (payload.title or candidate.title).strip()
    created = create_deadline(DeadlineCreate(title=title, due_at=payload.due_at, timezone=payload.timezone), student, db)
    deadline = _owned_deadline(db, student.id, created.id)
    deadline.source = "email"; deadline.source_ref = candidate.source_ref
    candidate.status = "confirmed"; candidate.confirmed_deadline_id = deadline.id; candidate.confirmed_at = datetime.now(timezone.utc)
    _audit(db, student.id, "deadline.extraction.confirmed", "deadline_candidate", candidate.id, "confirmed", {"deadline_id": deadline.id})
    db.commit()
    return _deadline(deadline)


@router.post("/deadline-candidates/{candidate_id}/reject")
def reject_deadline_candidate(candidate_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    candidate = db.scalar(select(AssistantDeadlineCandidate).where(AssistantDeadlineCandidate.id == candidate_id,
        AssistantDeadlineCandidate.student_id == student.id))
    if candidate is None: raise HTTPException(404, "Deadline candidate not found")
    if candidate.status != "needs_confirmation": raise HTTPException(409, "Deadline candidate was already reviewed")
    candidate.status = "rejected"; _audit(db, student.id, "deadline.extraction.rejected", "deadline_candidate", candidate.id, "rejected")
    db.commit(); return {"id": candidate.id, "status": candidate.status}


class ReplyDraftRequest(BaseModel):
    response_points: str = Field(min_length=1, max_length=1200)
    tone: str = Field(default="professional", pattern="^(formal|professional|casual)$")
    language: str = Field(default="en", pattern="^(en|te|mixed)$")


@router.post("/emails/{email_id}/draft", response_model=DraftView, status_code=201)
def draft_email_reply(email_id: str, payload: ReplyDraftRequest, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    email_row = db.scalar(select(AssistantEmailMessage).where(AssistantEmailMessage.id == email_id,
        AssistantEmailMessage.student_id == student.id))
    if email_row is None: raise HTTPException(404, "Email not found")
    try: body = generate_reply(email_row, payload.response_points, payload.tone, payload.language)
    except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
    except ProviderFailure: raise HTTPException(502, "Reply drafting is temporarily unavailable")
    recipient = parseaddr(email_row.sender)[1]
    if not recipient or "@" not in recipient: raise HTTPException(409, "Sender address is not available for a safe reply")
    risk = "low"
    if email_row.category == "security_or_financial": risk = "security"
    elif any(term in (email_row.subject + " " + email_row.snippet).casefold() for term in ("medical", "doctor", "contract", "legal", "job offer", "resign")):
        risk = "sensitive"
    row = AssistantDraft(student_id=student.id, thread_ref=email_row.thread_ref, recipient=recipient,
        subject=email_row.subject if email_row.subject.casefold().startswith("re:") else "Re: " + email_row.subject,
        body=body, risk_category=risk, rfc_message_id=email_row.rfc_message_id,
        references_header=email_row.references_header)
    db.add(row); db.flush(); _audit(db, student.id, "email.reply.drafted", "draft", row.id, "draft_only", {"tone": payload.tone})
    db.commit(); db.refresh(row); return row


class DraftUpdate(BaseModel):
    recipient: EmailStr | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=20000)


@router.patch("/drafts/{draft_id}", response_model=DraftView)
def edit_draft(draft_id: str, payload: DraftUpdate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _owned_draft(db, student.id, draft_id)
    if row.status not in {"draft", "rejected"}: raise HTTPException(409, "Only unsent drafts can be edited")
    changes = payload.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(422, "Provide at least one draft field")
    if any("\r" in str(v) or "\n" in str(v) for v in changes.values() if v is not None): raise HTTPException(422, "Email headers cannot contain line breaks")
    for key, value in changes.items(): setattr(row, key, str(value) if key == "recipient" else value)
    row.status = "draft"; row.approved_at = None; row.idempotency_key = None
    _audit(db, student.id, "email.draft.edited", "draft", row.id, "saved", {"changed": sorted(changes)})
    db.commit(); db.refresh(row); return row


class PhoneVerifyStart(BaseModel):
    phone: str = Field(min_length=8, max_length=16, pattern=r"^\+[1-9]\d{7,14}$")
    consent_to_verification_sms: bool


@router.post("/phone/verification/start")
def start_phone_verification(payload: PhoneVerifyStart, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if not payload.consent_to_verification_sms: raise HTTPException(422, "Explicit SMS consent is required")
    now = datetime.now(timezone.utc)
    recent = db.scalar(select(func.count(AssistantAuditEvent.id)).where(
        AssistantAuditEvent.student_id == student.id, AssistantAuditEvent.action == "phone.verification.started",
        AssistantAuditEvent.created_at >= now - timedelta(hours=1))) or 0
    if recent >= 3: raise HTTPException(429, "Verification SMS limit reached; try again later")
    row = _settings(db, student.id)
    if row.reminder_phone != payload.phone:
        row.reminder_phone = payload.phone; row.phone_verified = False; row.call_consent_at = None
    try: twilio_verify_start(payload.phone)
    except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
    except ProviderFailure: raise HTTPException(502, "Phone verification could not be started")
    _audit(db, student.id, "phone.verification.started", "phone", None, "sms_sent")
    db.commit()
    return {"status": "verification_pending", "phone_last_four": payload.phone[-4:]}


class PhoneVerifyCheck(BaseModel):
    code: str = Field(min_length=4, max_length=10, pattern=r"^\d+$")


@router.post("/phone/verification/confirm")
def confirm_phone_verification(payload: PhoneVerifyCheck, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    row = _settings(db, student.id)
    if not row.reminder_phone: raise HTTPException(409, "Set a phone number first")
    now = datetime.now(timezone.utc)
    failures = db.scalar(select(func.count(AssistantAuditEvent.id)).where(
        AssistantAuditEvent.student_id == student.id, AssistantAuditEvent.action == "phone.verification.rejected",
        AssistantAuditEvent.created_at >= now - timedelta(minutes=15))) or 0
    if failures >= 5: raise HTTPException(429, "Too many verification attempts; try again later")
    try: approved = twilio_verify_check(row.reminder_phone, payload.code)
    except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
    except ProviderFailure: raise HTTPException(502, "Phone verification could not be confirmed")
    if not approved:
        _audit(db, student.id, "phone.verification.rejected", "phone", None, "invalid_code")
        db.commit()
        raise HTTPException(422, "Verification code was not accepted")
    row.phone_verified = True
    _audit(db, student.id, "phone.verified", "phone", None, "verified")
    db.commit()
    return {"phone_verified": True, "call_consent": bool(row.call_consent_at)}


@router.get("/calls")
def list_calls(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    rows = db.scalars(select(AssistantCallAttempt).where(AssistantCallAttempt.student_id == student.id)
        .order_by(AssistantCallAttempt.created_at.desc()).limit(100)).all()
    return [{"id": row.id, "status": row.status, "provider_status": row.provider_status,
             "destination_last_four": row.destination[-4:], "failure_code": row.failure_code,
             "created_at": row.created_at, "updated_at": row.updated_at} for row in rows]


@router.post("/webhooks/twilio/status")
async def twilio_status_webhook(request: Request, db: Session = Depends(get_db)):
    cfg = get_settings()
    if not twilio_live_ready(cfg): raise HTTPException(503, "Telephony callbacks are unavailable")
    form = await request.form()
    grouped: dict[str, list[str]] = {}
    for key, value in form.multi_items(): grouped.setdefault(str(key), []).append(str(value))
    signature = request.headers.get("X-Twilio-Signature", "")
    if not verify_twilio_signature(cfg.twilio_status_callback_url, grouped, signature, cfg.twilio_auth_token):
        raise HTTPException(403, "Invalid telephony callback signature")
    sid = grouped.get("CallSid", [""])[0]
    account_sid = grouped.get("AccountSid", [""])[0]
    if not sid or account_sid != cfg.twilio_account_sid: raise HTTPException(400, "Invalid callback account")
    attempt = db.scalar(select(AssistantCallAttempt).where(AssistantCallAttempt.provider_sid == sid).with_for_update())
    if attempt is None: raise HTTPException(404, "Call attempt not found")
    called = grouped.get("To", [attempt.destination])[0]
    if called != attempt.destination: raise HTTPException(403, "Callback destination does not match")
    has_sequence = bool(grouped.get("SequenceNumber"))
    try: sequence = int(grouped.get("SequenceNumber", ["0"])[0])
    except ValueError: raise HTTPException(400, "Invalid callback sequence")
    status_value = grouped.get("CallStatus", [""])[0]
    allowed = {"queued", "initiated", "ringing", "in-progress", "completed", "busy", "failed", "no-answer", "canceled"}
    if status_value not in allowed: raise HTTPException(422, "Unsupported provider status")
    if has_sequence and sequence <= attempt.callback_sequence: return {"accepted": True, "duplicate": True}
    # Twilio callbacks do not include SequenceNumber in every Voice configuration.
    # When absent, use a monotonic lifecycle rank and reject repeats/regressions.
    rank = {"queued": 0, "initiated": 1, "ringing": 2, "in-progress": 3,
            "completed": 4, "busy": 4, "failed": 4, "no-answer": 4, "canceled": 4}
    old_status = attempt.provider_status
    if not has_sequence and old_status and (rank.get(status_value, -1) < rank.get(old_status, -1) or
                                             rank.get(status_value) == rank.get(old_status)):
        return {"accepted": True, "duplicate": True}
    if has_sequence: attempt.callback_sequence = sequence
    attempt.provider_status = status_value; attempt.updated_at = datetime.now(timezone.utc)
    job = db.get(AssistantJob, attempt.job_id)
    if status_value == "completed":
        attempt.status = "completed"; job.status = "completed"; job.provider_status = "completed"; job.last_error = None
    elif status_value in {"busy", "failed", "no-answer", "canceled"}:
        attempt.status = status_value; attempt.failure_code = "call_" + status_value
        if job.attempts < job.max_attempts:
            job.status = "retry"; job.run_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 30 * (2 ** max(0, job.attempts - 1))))
            job.last_error = attempt.failure_code
        else:
            job.status = "failed"; job.provider_status = status_value; job.last_error = attempt.failure_code
    else:
        attempt.status = status_value
        job.status = "waiting_callback"; job.provider_status = status_value
    _audit(db, attempt.student_id, "call.status.updated", "call", attempt.id, status_value)
    db.commit()
    return {"accepted": True}


class CalendarEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    starts_at: datetime
    ends_at: datetime
    timezone: str = Field(min_length=1, max_length=80)
    confirmed: bool = False

    @field_validator("starts_at", "ends_at")
    @classmethod
    def event_time_aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None: raise ValueError("Calendar times must have explicit timezone offsets")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Use an IANA timezone")
        return value

    @model_validator(mode="after")
    def time_order(self):
        if self.ends_at <= self.starts_at: raise ValueError("Event end must follow start")
        return self


@router.get("/calendar/events")
def calendar_events(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == student.id,
        AssistantAccount.provider == "calendar", AssistantAccount.status == "connected"))
    if account is None: raise HTTPException(409, "Connect Google Calendar first")
    try: list_calendar_events(db, student.id, account)
    except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
    except ProviderFailure as exc:
        account.last_error = exc.code
        if exc.code == "google_reauthorization_required": account.status = "reauthorization_required"
        db.commit(); raise HTTPException(502, "Calendar synchronization failed")
    db.commit()
    rows = db.scalars(select(AssistantCalendarEvent).where(AssistantCalendarEvent.student_id == student.id,
        AssistantCalendarEvent.starts_at >= datetime.now(timezone.utc)).order_by(AssistantCalendarEvent.starts_at).limit(100)).all()
    return [{"id": r.id, "title": r.title, "starts_at": r.starts_at, "ends_at": r.ends_at,
             "timezone": r.timezone_name, "external_id": r.external_id} for r in rows]


@router.post("/calendar/events")
def create_calendar_event_endpoint(payload: CalendarEventRequest, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    if not payload.confirmed: raise HTTPException(409, "Confirm the calendar event before creating it")
    account = db.scalar(select(AssistantAccount).where(AssistantAccount.student_id == student.id,
        AssistantAccount.provider == "calendar", AssistantAccount.status == "connected"))
    if account is None: raise HTTPException(409, "Connect Google Calendar first")
    dedupe = hashlib.sha256(f"{student.id}|{payload.title.casefold()}|{payload.starts_at.astimezone(timezone.utc).isoformat()}|{payload.ends_at.astimezone(timezone.utc).isoformat()}".encode()).hexdigest()
    try:
        event = create_calendar_event(db, student.id, account, title=payload.title.strip(), starts_at=payload.starts_at,
            ends_at=payload.ends_at, timezone_name=payload.timezone, dedupe_key=dedupe)
        _audit(db, student.id, "calendar.event.created", "calendar_event", event.id, "provider_confirmed")
        db.commit()
    except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
    except ProviderFailure: db.rollback(); raise HTTPException(502, "Calendar event creation failed or needs review")
    return {"id": event.id, "title": event.title, "starts_at": event.starts_at, "ends_at": event.ends_at,
            "timezone": event.timezone_name, "status": "created"}


class VoiceCommand(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="mixed", pattern="^(en|te|mixed)$")
    confirmed: bool = False
    title: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None
    thread_ref: str | None = Field(default=None, max_length=255)
    response_points: str | None = Field(default=None, max_length=1200)
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("due_at", "starts_at", "ends_at")
    @classmethod
    def explicit_zone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None): raise ValueError("Use an explicit timezone")
        return value


@router.post("/voice/transcribe")
def transcribe_assistant_voice(audio: UploadFile = File(...), student: Student = Depends(current_student)):
    filename = Path(audio.filename or "").name
    if Path(filename).suffix.casefold() != ".wav": raise HTTPException(415, "Upload an uncompressed PCM WAV file")
    data = audio.file.read(10 * 1024 * 1024 + 1)
    if not data: raise HTTPException(422, "Audio is empty")
    if len(data) > 10 * 1024 * 1024: raise HTTPException(413, "Audio exceeds 10 MB")
    try:
        with tempfile.TemporaryDirectory(prefix="bhashalearn-assistant-stt-") as folder:
            path = Path(folder) / "command.wav"; path.write_bytes(data); validate_audio(path)
            provider = create_prisma_client()
            result = PrismaTranscriptionAdapter(provider).transcribe(path)
            return {"transcript": result.text, "detected_language": result.detected_language}
    except VoiceProviderNotConfigured as exc: raise HTTPException(503, str(exc)) from exc
    except STTStageError as exc:
        raise HTTPException(504 if exc.code == "timeout" else 502, "Gnani speech recognition is unavailable") from exc
    except STTError as exc: raise HTTPException(422, str(exc)) from exc


class AssistantSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    language: str = Field(default="mixed", pattern="^(en|te|mixed)$")


@router.post("/voice/speech")
def speak_assistant_response(payload: AssistantSpeechRequest, student: Student = Depends(current_student)):
    language = {"en": "english", "te": "telugu", "mixed": "mixed"}[payload.language]
    try:
        with tempfile.TemporaryDirectory(prefix="bhashalearn-assistant-tts-") as folder:
            adapter = create_timbre_adapter(folder)
            artifact = adapter.synthesize_response(payload.text.strip(), Language(language), "assistant-command")
            return Response(artifact.path.read_bytes(), media_type="audio/wav", headers={
                "Cache-Control": "no-store", "X-Audio-Sample-Rate": str(artifact.sample_rate)})
    except VoiceProviderNotConfigured as exc: raise HTTPException(503, str(exc)) from exc
    except TTSStageError as exc: raise HTTPException(504 if exc.code == "timeout" else 502, "Gnani speech synthesis is unavailable") from exc


@router.post("/voice/commands")
def voice_command(payload: VoiceCommand, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    text = payload.text.strip()
    lowered = text.casefold()
    if any(term in lowered for term in ("upcoming", "next reminder", "upcoming reminders", "రాబోయే", "తదుపరి రిమైండర్")):
        rows = db.scalars(select(AssistantDeadline).where(AssistantDeadline.student_id == student.id,
            AssistantDeadline.status.in_(["upcoming", "overdue"])).order_by(AssistantDeadline.due_at).limit(10)).all()
        return {"intent": "upcoming_reminders", "requires_confirmation": False, "items": [_deadline(r).model_dump() for r in rows]}
    if any(term in lowered for term in ("inbox summary", "summarize inbox", "read my inbox", "ఇన్‌బాక్స్", "మెయిల్ సారాంశం")):
        items = db.scalars(select(AssistantEmailMessage).where(AssistantEmailMessage.student_id == student.id)
            .order_by(AssistantEmailMessage.internal_date.desc()).limit(5)).all()
        if not items: raise HTTPException(409, "No authorized Gmail inbox is synchronized")
        return {"intent": "inbox_summary", "requires_confirmation": False,
                "items": [{"subject": row.subject, "sender": row.sender, "category": row.category, "snippet": row.snippet} for row in items]}
    if any(term in lowered for term in ("deadline", "remind me", "create reminder", "గడువు", "గుర్తు చేయి")):
        title = payload.title; due_at = payload.due_at
        if title is None or due_at is None:
            candidate = re.sub(r"^(?:create\s+)?(?:deadline|reminder|remind\s+me|గడువు|గుర్తు\s+చేయి)\s*[:,-]?\s*", "", text, flags=re.I)
            match = re.match(r"(.+?)\s+(?:due\s+)?(?:at|on)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))$", candidate, flags=re.I)
            if match:
                title = re.sub(r"\s+due$", "", match.group(1), flags=re.I).strip()
                try: due_at = datetime.fromisoformat(match.group(2).replace("Z", "+00:00"))
                except ValueError: due_at = None
        if not title or not due_at:
            return {"intent": "create_deadline", "requires_confirmation": False,
                    "needs_input": ["title", "timezone-aware due_at"], "message": "Include an ISO date/time with Z or an offset such as +05:30."}
        if not payload.confirmed:
            return {"intent": "create_deadline", "requires_confirmation": True, "preview": {"title": title, "due_at": due_at.isoformat()}}
        created = create_deadline(DeadlineCreate(title=title, due_at=due_at), student, db)
        return {"intent": "create_deadline", "requires_confirmation": False, "deadline": created.model_dump()}
    if any(term in lowered for term in ("calendar", "event", "క్యాలెండర్", "ఈవెంట్")):
        title = payload.title; starts_at = payload.starts_at; ends_at = payload.ends_at
        if title is None or starts_at is None or ends_at is None:
            candidate = re.sub(r"^(?:calendar\s+)?(?:event|meeting|క్యాలెండర్|ఈవెంట్)\s*[:,-]?\s*", "", text, flags=re.I)
            match = re.match(r"(.+?)\s+(?:from|at)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))\s+(?:to|until)\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2}))$", candidate, flags=re.I)
            if match:
                title = match.group(1).strip()
                try:
                    starts_at = datetime.fromisoformat(match.group(2).replace("Z", "+00:00"))
                    ends_at = datetime.fromisoformat(match.group(3).replace("Z", "+00:00"))
                except ValueError: starts_at = ends_at = None
        if not title or not starts_at or not ends_at: raise HTTPException(422, "Provide a title, start and end with timezone offsets")
        if not payload.confirmed:
            return {"intent": "calendar_event", "requires_confirmation": True, "preview": {
                "title": title, "starts_at": starts_at.isoformat(), "ends_at": ends_at.isoformat()}}
        calendar_payload = CalendarEventRequest(title=title, starts_at=starts_at, ends_at=ends_at,
            timezone=_settings(db, student.id).timezone_name, confirmed=True)
        return create_calendar_event_endpoint(calendar_payload, student, db)
    if any(term in lowered for term in ("draft email", "draft a reply", "ఇమెయిల్ డ్రాఫ్ట్", "సమాధానం తయారు")):
        thread_ref = payload.thread_ref; response_points = payload.response_points
        if not thread_ref or not response_points:
            match = re.match(r".*?(?:reply|email|డ్రాఫ్ట్).*?(?:thread\s+)?([A-Za-z0-9_-]{5,255})\s*[:,-]\s*(.+)$", text, flags=re.I)
            if match: thread_ref = thread_ref or match.group(1); response_points = response_points or match.group(2).strip()
        if not thread_ref or not response_points:
            return {"intent": "draft_email", "requires_confirmation": False, "needs_input": ["thread_ref", "response_points"]}
        email_row = db.scalar(select(AssistantEmailMessage).where(AssistantEmailMessage.student_id == student.id,
            AssistantEmailMessage.thread_ref == thread_ref).order_by(AssistantEmailMessage.internal_date.desc()))
        if email_row is None: raise HTTPException(404, "Authorized email thread not found")
        try: body = generate_reply(email_row, response_points, "professional", payload.language)
        except ProviderUnavailable as exc: raise HTTPException(503, str(exc))
        except ProviderFailure: raise HTTPException(502, "Reply drafting is temporarily unavailable")
        recipient = parseaddr(email_row.sender)[1]
        if not recipient: raise HTTPException(409, "Sender address is not available")
        draft = AssistantDraft(student_id=student.id, thread_ref=email_row.thread_ref, recipient=recipient,
            subject="Re: " + email_row.subject, body=body, risk_category="uncertain")
        db.add(draft); db.flush(); _audit(db, student.id, "email.reply.drafted", "draft", draft.id, "draft_only")
        db.commit(); return {"intent": "draft_email", "requires_confirmation": False, "draft": DraftView.model_validate(draft).model_dump()}
    raise HTTPException(422, "Command not recognized; try a deadline, upcoming reminders, email draft, calendar event, or inbox summary command")


@router.get("/activity/calls")
def call_activity_alias(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return list_calls(student, db)


@router.get("/activity")
def activity(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    events = db.scalars(select(AssistantAuditEvent).where(AssistantAuditEvent.student_id == student.id).order_by(AssistantAuditEvent.created_at.desc()).limit(100)).all()
    return [{"id": e.id, "action": e.action, "target_type": e.target_type, "target_id": e.target_id,
             "outcome": e.outcome, "created_at": e.created_at, "details": _json(e.details_json, {})} for e in events]
