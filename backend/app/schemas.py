from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class DeadlineIn(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    kind: Literal["assignment", "exam"] = "assignment"
    due_at: datetime
    timezone: str = "Asia/Kolkata"
    notes: str | None = None

    @field_validator("due_at")
    @classmethod
    def require_aware_due_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must include a timezone offset")
        return value

    @field_validator("timezone")
    @classmethod
    def require_known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class DeadlineOut(DeadlineIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    deadline_id: UUID
    scheduled_at: datetime
    channel: str
    status: str
    attempts: int
    snoozed_until: datetime | None


class PreferencesIn(BaseModel):
    timezone: str = "Asia/Kolkata"
    language: Literal["te-IN", "en-IN", "auto"] = "te-IN"
    voice_enabled: bool = True
    call_enabled: bool = False
    consent: bool = False


class ReminderAction(BaseModel):
    action: Literal["acknowledge", "completed", "snooze", "reschedule", "cancel"]
    until: datetime | None = None
    detail: str | None = None

