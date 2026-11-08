"""Student-owned Mission Mode progress and idempotent XP claims."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import LearningAssessmentAttempt, MissionCompletion, Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/missions", tags=["mission mode"])


@dataclass(frozen=True)
class Mission:
    id: str
    title: str
    subject: str
    topic_key: str
    description: str
    objective: str
    target: int
    xp: int
    daily: bool = False
    day: date | None = None


def mission_catalog(today: date | None = None) -> list[Mission]:
    today = today or datetime.now(timezone.utc).date()
    # Stable definitions that map directly to the built-in objective assessment bank.
    missions = [
        Mission("quest-fractions", "Fraction Explorer", "Mathematics", "equivalent fractions",
                "Build confidence with equivalent fractions.", "Answer 3 fraction questions correctly", 3, 60),
        Mission("quest-pathfinder", "Pathfinder", "Computer Science", "dijkstra shortest path",
                "Practice choosing the shortest route through a graph.", "Answer 3 shortest-path questions correctly", 3, 75),
    ]
    daily_topics = [
        ("equivalent fractions", "Mathematics", "Fraction Flash", "Solve one fraction question today"),
        ("dijkstra shortest path", "Computer Science", "Daily Pathfinder", "Solve one shortest-path question today"),
    ]
    topic, subject, title, objective = daily_topics[today.toordinal() % len(daily_topics)]
    missions.append(Mission(
        f"daily-{today.isoformat()}", title, subject, topic,
        "A fresh one-question challenge, available for this UTC day.", objective, 1, 25, True, today,
    ))
    return missions


def _counts(db: Session, student_id: str, mission: Mission) -> int:
    stmt = select(func.count(LearningAssessmentAttempt.id)).where(
        LearningAssessmentAttempt.student_id == student_id,
        LearningAssessmentAttempt.normalized_topic_key == mission.topic_key,
        LearningAssessmentAttempt.is_correct.is_(True),
    )
    if mission.daily and mission.day:
        start = datetime.combine(mission.day, time.min, tzinfo=timezone.utc)
        stmt = stmt.where(LearningAssessmentAttempt.answered_at >= start,
                          LearningAssessmentAttempt.answered_at < start + timedelta(days=1))
    return int(db.scalar(stmt) or 0)


def _mission_record(db: Session, student_id: str, mission: Mission, completion: MissionCompletion | None) -> dict:
    progress = min(_counts(db, student_id, mission), mission.target)
    return {
        "id": mission.id, "title": mission.title, "subject": mission.subject,
        "description": mission.description, "objective": mission.objective,
        "progress": progress, "target": mission.target, "xp_reward": mission.xp,
        "completed": completion is not None,
        "eligible": completion is None and progress >= mission.target,
        "completed_at": completion.completed_at if completion else None,
        "daily": mission.daily, "active_date": mission.day.isoformat() if mission.day else None,
    }


class MissionCard(BaseModel):
    id: str
    title: str
    subject: str
    description: str
    objective: str
    progress: int
    target: int
    xp_reward: int
    completed: bool
    eligible: bool
    completed_at: datetime | None
    daily: bool
    active_date: str | None


class MissionOverview(BaseModel):
    missions: list[MissionCard]
    xp: int
    level: int
    xp_into_level: int
    xp_to_next_level: int
    badges: list[str]


class ClaimResponse(BaseModel):
    mission: MissionCard
    xp_awarded: int
    total_xp: int
    level: int
    replayed: bool
    feedback: str


def _overview(db: Session, student_id: str) -> MissionOverview:
    completions = db.scalars(select(MissionCompletion).where(MissionCompletion.student_id == student_id)).all()
    by_id = {row.mission_id: row for row in completions}
    total_xp = sum(row.xp_awarded for row in completions)
    level = total_xp // 100 + 1
    badges = []
    if completions:
        badges.append("First Steps")
    if len(completions) >= 3:
        badges.append("Quest Keeper")
    if total_xp >= 250:
        badges.append("XP Champion")
    return MissionOverview(
        missions=[_mission_record(db, student_id, mission, by_id.get(mission.id))
                  for mission in mission_catalog()],
        xp=total_xp, level=level, xp_into_level=total_xp % 100,
        xp_to_next_level=100 - (total_xp % 100), badges=badges,
    )


@router.get("", response_model=MissionOverview)
def get_missions(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    return _overview(db, student.id)


@router.post("/{mission_id}/claim", response_model=ClaimResponse)
def claim_mission(mission_id: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    mission = next((item for item in mission_catalog() if item.id == mission_id), None)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    existing = db.scalar(select(MissionCompletion).where(
        MissionCompletion.student_id == student.id, MissionCompletion.mission_id == mission.id
    ))
    if existing is not None:
        overview = _overview(db, student.id)
        card = next(card for card in overview.missions if card.id == mission.id)
        return ClaimResponse(mission=card, xp_awarded=0, total_xp=overview.xp, level=overview.level,
                             replayed=True, feedback="Mission already claimed. Your XP is safe.")
    if _counts(db, student.id, mission) < mission.target:
        raise HTTPException(status_code=409, detail="Complete the mission objective before claiming its reward.")
    completion = MissionCompletion(student_id=student.id, mission_id=mission.id, xp_awarded=mission.xp)
    db.add(completion)
    try:
        db.commit()
    except IntegrityError:
        # The unique student/mission key is the final guard under concurrent retries.
        db.rollback()
        existing = db.scalar(select(MissionCompletion).where(
            MissionCompletion.student_id == student.id, MissionCompletion.mission_id == mission.id
        ))
        if existing is None:
            raise
        overview = _overview(db, student.id)
        card = next(card for card in overview.missions if card.id == mission.id)
        return ClaimResponse(mission=card, xp_awarded=0, total_xp=overview.xp, level=overview.level,
                             replayed=True, feedback="Mission already claimed. Your XP is safe.")
    overview = _overview(db, student.id)
    card = next(card for card in overview.missions if card.id == mission.id)
    return ClaimResponse(mission=card, xp_awarded=mission.xp, total_xp=overview.xp, level=overview.level,
                         replayed=False, feedback=f"Mission complete! +{mission.xp} XP earned.")
