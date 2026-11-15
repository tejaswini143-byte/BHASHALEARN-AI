"""Student registration, login, and authenticated profile endpoints."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import logging
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from backend.app.config import get_settings
from backend.app.db.models import PasswordResetToken, Student
from backend.app.db.session import get_db
from backend.app.services.password_reset_email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: EmailStr
    display_name: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetComplete(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class PasswordResetMessage(BaseModel):
    message: str


@router.post("/register", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(Student.id).where(Student.email == email)) is not None:
        raise HTTPException(status_code=409, detail="Email already registered")
    student = Student(email=email, display_name=payload.display_name.strip(), password_hash=hash_password(payload.password))
    if not student.display_name:
        raise HTTPException(status_code=422, detail="Display name cannot be blank")
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    db.refresh(student)
    return student


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    student = db.scalar(select(Student).where(Student.email == str(payload.email).lower()))
    if student is None or not student.password_hash or not verify_password(payload.password, student.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(student.id))


@router.post("/password-reset/request", response_model=PasswordResetMessage, status_code=202)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """Send an expiring, one-use reset link without revealing whether an account exists."""
    config = get_settings()
    if not all((config.smtp_host.strip(), config.smtp_from_email.strip(), config.app_public_base_url.strip())):
        raise HTTPException(status_code=503, detail="Password recovery email is not configured.")
    student = db.scalar(select(Student).where(Student.email == str(payload.email).lower()))
    if student is not None:
        raw_token = token_urlsafe(36)
        token_hash = sha256(raw_token.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc)
        db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
        db.add(PasswordResetToken(student_id=student.id, token_hash=token_hash, created_at=now,
                                  expires_at=now + timedelta(minutes=30)))
        db.commit()
        base = config.app_public_base_url.rstrip("/")
        reset_url = f"{base}/reset-password?token={quote(raw_token)}"
        try:
            send_password_reset_email(config, student.email, reset_url)
        except Exception:
            # Invalidate the token and keep response status/body independent of
            # account existence so this endpoint cannot be used for enumeration.
            db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
            db.commit()
            logger.warning("Password reset email delivery failed; token invalidated")
    return PasswordResetMessage(message="If an account exists for that address, a reset link will be sent.")


@router.post("/password-reset/complete", response_model=PasswordResetMessage)
def complete_password_reset(payload: PasswordResetComplete, db: Session = Depends(get_db)):
    token_hash = sha256(payload.token.encode("utf-8")).hexdigest()
    reset = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))
    now = datetime.now(timezone.utc)
    expires_at = reset.expires_at if reset is not None else None
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if reset is None or expires_at <= now:
        if reset is not None:
            db.delete(reset)
            db.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired. Request a new one.")
    student = db.get(Student, reset.student_id)
    if student is None:
        db.delete(reset)
        db.commit()
        raise HTTPException(status_code=400, detail="This reset link is invalid or expired. Request a new one.")
    student.password_hash = hash_password(payload.password)
    db.query(PasswordResetToken).filter(PasswordResetToken.student_id == student.id).delete()
    db.commit()
    return PasswordResetMessage(message="Your password has been updated. Sign in with the new password.")


def current_student(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Student:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing bearer token", headers={"WWW-Authenticate": "Bearer"})
    student_id = decode_access_token(credentials.credentials)
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=401, detail="Student no longer exists", headers={"WWW-Authenticate": "Bearer"})
    return student


@router.get("/me", response_model=StudentResponse)
def me(student: Student = Depends(current_student)):
    return student
