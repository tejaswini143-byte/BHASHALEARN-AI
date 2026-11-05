"""Student-owned learning memory CRUD API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.api.auth import current_student
from backend.app.db.models import LearningMemory, Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/memories", tags=["learning memory"])

class MemoryCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    note: str = Field(min_length=1, max_length=2000)

    @field_validator("topic", "note")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cannot be blank")
        return value

class MemoryResponse(MemoryCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime

def owned_memory(memory_id: str, student: Student, db: Session) -> LearningMemory:
    memory = db.get(LearningMemory, memory_id)
    if memory is None or memory.student_id != student.id:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory

@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(payload: MemoryCreate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    memory = LearningMemory(student_id=student.id, **payload.model_dump())
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory

@router.get("", response_model=list[MemoryResponse])
def list_memories(
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    topic: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
):
    stmt = select(LearningMemory).where(LearningMemory.student_id == student.id)
    if topic:
        stmt = stmt.where(LearningMemory.topic == topic)
    return db.scalars(stmt.order_by(LearningMemory.created_at.desc(), LearningMemory.id.desc()).limit(limit)).all()

@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(memory_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return owned_memory(memory_id, student, db)

@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(memory_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    db.delete(owned_memory(memory_id, student, db))
    db.commit()
