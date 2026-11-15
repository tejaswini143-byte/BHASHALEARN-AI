"""Standalone demo authentication for this isolated feature package."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .api import db_session
from .models import Student
from .settings import settings

router = APIRouter(prefix="/api/auth", tags=["demo authentication"])


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.urlsafe_b64encode(salt).decode() + "$" + base64.urlsafe_b64encode(digest).decode()


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt, expected = encoded.split("$", 2)
        if algorithm != "scrypt":
            return False
        digest = hashlib.scrypt(password.encode(), salt=base64.urlsafe_b64decode(salt), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def _issue_token(student_id: UUID) -> dict[str, str]:
    if settings.app_env.lower() not in {"development", "test"} and settings.jwt_secret == "development-only-change-me":
        raise HTTPException(503, "Set a production JWT_SECRET before enabling authentication")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(student_id), "iat": now, "exp": now + timedelta(hours=1), "type": "access"},
                       settings.jwt_secret, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(db_session)):
    email = str(body.email).lower()
    if db.scalar(select(Student.id).where(Student.email == email)):
        raise HTTPException(409, "Email already registered")
    student = Student(email=email, password_hash=_hash_password(body.password))
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Email already registered") from exc
    db.refresh(student)
    return {"student_id": str(student.id), **_issue_token(student.id)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(db_session)):
    student = db.scalar(select(Student).where(Student.email == str(body.email).lower()))
    if student is None or not _verify_password(body.password, student.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return {"student_id": str(student.id), **_issue_token(student.id)}
