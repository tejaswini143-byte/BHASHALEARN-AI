"""Student registration, login, and authenticated profile endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from backend.app.db.models import Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)


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
