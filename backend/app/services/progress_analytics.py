"""Bounded, deterministic analytics built only from recorded learning events.

All calendar boundaries use UTC. Naive legacy timestamps are treated as UTC,
matching the application's historical UTC timestamp convention.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import Date, String, cast, func, select
from sqlalchemy.orm import Session

from backend.app.db.models import (
    LearningAssessmentAttempt,
    LearningProgress,
    LearningSession,
    MissionCompletion,
)
from backend.app.services.adaptive_learning import normalize_topic, recommend

UTC = timezone.utc
ALLOWED_RANGES = (7, 30, 90)
MAX_TOPIC_ROWS = 200
MAX_TIMELINE_PER_SOURCE = 12
MAX_STREAK_DAYS = 370


@dataclass(frozen=True)
class ActivityEvent:
    kind: str
    title: str
    occurred_at: datetime
    detail: str | None = None


def utc_day_expression(db: Session, column):
    """Return a date key independent of PostgreSQL's configured session TZ."""
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        return cast(func.timezone("UTC", column), Date)
    if dialect == "sqlite":
        return func.strftime("%Y-%m-%d", column)
    # The application supports PostgreSQL and SQLite. The cast is a safe
    # fallback for compatible SQL dialects with timezone-aware timestamps.
    return cast(column, Date)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _subject_for(topic: str) -> str:
    """Conservative taxonomy; unknown free-text topics remain explicitly Other."""
    key = normalize_topic(topic)
    if key == "equivalent fractions":
        return "Mathematics"
    if key == "dijkstra shortest path":
        return "Computer Science"
    if any(word in key for word in ("english", "telugu", "grammar", "vocabulary", "greeting", "language")):
        return "Languages"
    return "Other"


def _adaptation_for(row: LearningProgress, student_id: str, db: Session) -> tuple[str, str, str]:
    outcomes = db.scalars(
        select(LearningAssessmentAttempt.is_correct)
        .where(
            LearningAssessmentAttempt.student_id == student_id,
            LearningAssessmentAttempt.normalized_topic_key == row.normalized_topic_key,
            LearningAssessmentAttempt.is_correct.is_not(None),
        )
        .order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(5)
    ).all()
    policy = recommend(
        max(0, row.evidence_attempts), max(0, row.correct_attempts),
        max(0, row.incorrect_attempts), tuple(bool(value) for value in reversed(outcomes)),
    )
    return policy.recommendation, policy.reason, policy.strategy


def build_analytics(db: Session, student_id: str, range_days: int, now: datetime | None = None) -> dict:
    """Aggregate one authenticated student's recorded activity for a bounded window."""
    if range_days not in ALLOWED_RANGES:
        raise ValueError("range_days must be one of 7, 30, or 90")
    now = _aware_utc(now or datetime.now(UTC))
    today = now.date()
    start_day = today - timedelta(days=range_days - 1)
    start_at = datetime.combine(start_day, time.min, tzinfo=UTC)
    end_at = datetime.combine(today + timedelta(days=1), time.min, tzinfo=UTC)

    sessions_total = int(db.scalar(
        select(func.count(LearningSession.id)).where(LearningSession.student_id == student_id)
    ) or 0)
    assessment_total = int(db.scalar(
        select(func.count(LearningAssessmentAttempt.id)).where(
            LearningAssessmentAttempt.student_id == student_id,
            LearningAssessmentAttempt.answered_at.is_not(None),
        )
    ) or 0)
    mission_total = int(db.scalar(
        select(func.count(MissionCompletion.id)).where(MissionCompletion.student_id == student_id)
    ) or 0)
    xp_total = int(db.scalar(
        select(func.coalesce(func.sum(MissionCompletion.xp_awarded), 0)).where(
            MissionCompletion.student_id == student_id,
        )
    ) or 0)

    # Grouped SQL reads are date-bounded; no conversation content or memory text
    # enters analytics. `func.date` is UTC-normalized per supported dialect.
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "assessments": 0, "missions": 0})
    for model, timestamp, key in (
        (LearningSession, LearningSession.created_at, "sessions"),
        (LearningAssessmentAttempt, LearningAssessmentAttempt.answered_at, "assessments"),
        (MissionCompletion, MissionCompletion.completed_at, "missions"),
    ):
        date_key = utc_day_expression(db, timestamp)
        stmt = (
            select(date_key.label("day"), func.count(model.id).label("total"))
            .where(model.student_id == student_id, timestamp >= start_at, timestamp < end_at)
            .group_by(date_key).order_by(date_key)
        )
        if model is LearningAssessmentAttempt:
            stmt = stmt.where(timestamp.is_not(None))
        for item in db.execute(stmt):
            day = item.day.isoformat() if isinstance(item.day, date) else str(item.day)
            buckets[day][key] = int(item.total)

    trend = [
        {"date": (start_day + timedelta(days=index)).isoformat(),
         "sessions": buckets[(start_day + timedelta(days=index)).isoformat()]["sessions"],
         "completed_assessments": buckets[(start_day + timedelta(days=index)).isoformat()]["assessments"],
         "mission_completions": buckets[(start_day + timedelta(days=index)).isoformat()]["missions"],
         "activity_count": sum(buckets[(start_day + timedelta(days=index)).isoformat()].values())}
        for index in range(range_days)
    ]
    range_assessment_count = sum(item["completed_assessments"] for item in trend)
    range_session_count = sum(item["sessions"] for item in trend)
    range_mission_count = sum(item["mission_completions"] for item in trend)

    topic_stmt = (
        select(
            LearningProgress.topic,
            LearningProgress.normalized_topic_key,
            LearningProgress.evidence_attempts,
            LearningProgress.correct_attempts,
            LearningProgress.incorrect_attempts,
            LearningProgress.ambiguous_attempts,
            LearningProgress.evidence_status,
            LearningProgress.last_assessed_at,
        )
        .where(LearningProgress.student_id == student_id)
        .order_by(LearningProgress.evidence_attempts.desc(), LearningProgress.topic.asc(), LearningProgress.id.asc())
        .limit(MAX_TOPIC_ROWS)
    )
    topic_rows = db.execute(topic_stmt).all()
    topics = []
    for row in topic_rows:
        attempts = max(0, int(row.evidence_attempts or 0))
        correct = min(attempts, max(0, int(row.correct_attempts or 0)))
        score = round(100 * correct / attempts, 1) if attempts else None
        topics.append({
            "topic": row.topic,
            "subject": _subject_for(row.topic),
            "mastery_score": score,
            "scored_attempts": attempts,
            "correct_attempts": correct,
            "incorrect_attempts": max(0, int(row.incorrect_attempts or 0)),
            "ambiguous_attempts": max(0, int(row.ambiguous_attempts or 0)),
            "evidence_status": row.evidence_status or "unassessed",
            "last_assessed_at": _aware_utc(row.last_assessed_at).isoformat() if row.last_assessed_at else None,
        })

    scored_topics = [item for item in topics if item["mastery_score"] is not None]
    subject_totals: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for item in scored_topics:
        values = subject_totals[item["subject"]]
        values[0] += item["correct_attempts"]
        values[1] += item["scored_attempts"]
    subjects = [
        {"subject": subject, "mastery_score": round(100 * correct / attempts, 1), "scored_attempts": attempts}
        for subject, (correct, attempts) in sorted(subject_totals.items(), key=lambda pair: pair[0].casefold())
        if attempts
    ]
    strengths = sorted(
        (item for item in scored_topics if item["scored_attempts"] >= 3),
        key=lambda item: (-item["mastery_score"], -item["scored_attempts"], item["topic"].casefold()),
    )[:3]
    improvement = sorted(
        (item for item in scored_topics if item["scored_attempts"] >= 1),
        key=lambda item: (item["mastery_score"], -item["scored_attempts"], item["topic"].casefold()),
    )[:3]

    # Recommendations are generated from recorded evidence and the same policy
    # used by adaptive learning. Unassessed progress gets a diagnostic prompt.
    recommendations = []
    recommendation_rows = sorted(
        (row for row in topic_rows if int(row.evidence_attempts or 0) > 0),
        key=lambda row: (100 * int(row.correct_attempts or 0) / max(1, int(row.evidence_attempts or 0)), row.topic.casefold()),
    )
    for row in recommendation_rows[:3]:
        recommendation, reason, _ = _adaptation_for(row, student_id, db)
        recommendations.append({"topic": row.topic, "recommendation": recommendation, "reason": reason})
    if not recommendations:
        recommendations.append({
            "topic": None,
            "recommendation": "Start a short objective practice to establish your first learning baseline.",
            "reason": "No scored assessment answers are recorded yet.",
        })

    # Activity streak includes dated session starts, answered assessment events,
    # and unique mission claims. It is calculated in UTC, capped to a bounded
    # lookback; a true streak beyond the cap is marked as a lower bound.
    activity_days: set[date] = set()
    streak_start = datetime.combine(today - timedelta(days=MAX_STREAK_DAYS - 1), time.min, tzinfo=UTC)
    for model, timestamp in (
        (LearningSession, LearningSession.created_at),
        (LearningAssessmentAttempt, LearningAssessmentAttempt.answered_at),
        (MissionCompletion, MissionCompletion.completed_at),
    ):
        date_key = utc_day_expression(db, timestamp)
        stmt = (
            select(date_key.label("day"))
            .where(model.student_id == student_id, timestamp >= streak_start, timestamp < end_at)
            .group_by(date_key).order_by(date_key.desc()).limit(MAX_STREAK_DAYS)
        )
        if model is LearningAssessmentAttempt:
            stmt = stmt.where(timestamp.is_not(None))
        for item in db.execute(stmt):
            try:
                activity_days.add(date.fromisoformat(item.day.isoformat() if isinstance(item.day, date) else str(item.day)))
            except ValueError:
                continue
    cursor = today if today in activity_days else today - timedelta(days=1)
    streak = 0
    while cursor in activity_days:
        streak += 1
        cursor -= timedelta(days=1)
    streak_lower_bound = streak == MAX_STREAK_DAYS

    timeline: list[ActivityEvent] = []
    session_rows = db.scalars(
        select(LearningSession).where(LearningSession.student_id == student_id)
        .order_by(LearningSession.created_at.desc(), LearningSession.id.desc()).limit(MAX_TIMELINE_PER_SOURCE)
    ).all()
    timeline.extend(ActivityEvent("session", f"Started {row.topic}", row.created_at, row.language) for row in session_rows)
    assessment_rows = db.execute(
        select(LearningAssessmentAttempt.topic, LearningAssessmentAttempt.is_correct, LearningAssessmentAttempt.answered_at,
               LearningAssessmentAttempt.id)
        .where(LearningAssessmentAttempt.student_id == student_id, LearningAssessmentAttempt.answered_at.is_not(None))
        .order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(MAX_TIMELINE_PER_SOURCE)
    ).all()
    timeline.extend(
        ActivityEvent(
            "assessment", f"Practiced {row.topic}", row.answered_at,
            "Correct" if row.is_correct is True else "Review suggested" if row.is_correct is False else "Answer recorded",
        ) for row in assessment_rows
    )
    mission_rows = db.scalars(
        select(MissionCompletion).where(MissionCompletion.student_id == student_id)
        .order_by(MissionCompletion.completed_at.desc(), MissionCompletion.id.desc()).limit(MAX_TIMELINE_PER_SOURCE)
    ).all()
    timeline.extend(
        ActivityEvent("mission", "Mission completed", row.completed_at, f"+{row.xp_awarded} XP")
        for row in mission_rows
    )
    timeline.sort(key=lambda event: (_aware_utc(event.occurred_at), event.kind, event.title), reverse=True)

    level = xp_total // 100 + 1
    badges = []
    if mission_total:
        badges.append("First Steps")
    if mission_total >= 3:
        badges.append("Quest Keeper")
    if xp_total >= 250:
        badges.append("XP Champion")

    return {
        "range_days": range_days,
        "timezone": "UTC",
        "date_rule": "UTC calendar days; today and the preceding range_days - 1 days, ending at the next UTC midnight.",
        "overview": {
            "learning_sessions": sessions_total,
            "completed_activities": assessment_total + mission_total,
            "completed_assessments": assessment_total,
            "learning_time_minutes": None,
            "learning_time_status": "not_recorded",
        },
        "range_totals": {
            "sessions": range_session_count,
            "completed_assessments": range_assessment_count,
            "mission_completions": range_mission_count,
        },
        "trend": trend,
        "topics": topics,
        "subjects": subjects,
        "strengths": [{"topic": item["topic"], "mastery_score": item["mastery_score"], "scored_attempts": item["scored_attempts"]} for item in strengths],
        "improvement_areas": [{"topic": item["topic"], "mastery_score": item["mastery_score"], "scored_attempts": item["scored_attempts"]} for item in improvement],
        "mission": {
            "xp": xp_total,
            "level": level,
            "xp_into_level": xp_total % 100,
            "xp_to_next_level": 100 - xp_total % 100,
            "completed_missions": mission_total,
            "badges": badges,
        },
        "streak": {"days": streak, "as_of_utc_date": today.isoformat(), "timezone": "UTC", "lower_bound": streak_lower_bound},
        "recent_activity": [
            {"kind": event.kind, "title": event.title, "occurred_at": _aware_utc(event.occurred_at).isoformat(), "detail": event.detail}
            for event in timeline[:12]
        ],
        "recommendations": recommendations,
        "quiz_analytics": {"available": False, "integration": "Future quiz adapters may provide completed, student-owned scored outcomes; current analytics remains independent."},
    }
