"""LiveKit Agents worker bound to BHASHALEARN's production SQLAlchemy models."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool, stt, tokenize
from livekit.plugins import google, silero
from sqlalchemy import select

from backend.app.config import get_settings
from backend.app.db.models import AssistantDeadline, AssistantJob, AssistantLiveKitSession, AssistantSettings, new_id
from backend.app.db.session import get_session_factory
from backend.app.services.assistant_livekit_adapters import GnaniPrismaSTT, GnaniTimbreTTS

server = AgentServer()


def _read_context(session_id: str):
    factory = get_session_factory()
    with factory() as db:
        row = db.get(AssistantLiveKitSession, session_id)
        if row is None or row.status not in {"creating", "dispatched", "active"}:
            return None
        deadline = db.scalar(select(AssistantDeadline).where(
            AssistantDeadline.id == row.deadline_id, AssistantDeadline.student_id == row.student_id))
        if deadline is None or deadline.status not in {"upcoming", "overdue"}:
            return None
        prefs = db.get(AssistantSettings, row.student_id)
        return row.student_id, deadline.id, deadline.title, deadline.due_at, deadline.timezone_name, row.language, bool(prefs and prefs.paused)


def _apply_intent(student_id: str, deadline_id: str, session_id: str, action: str, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    with get_session_factory().begin() as db:
        deadline = db.scalar(select(AssistantDeadline).where(
            AssistantDeadline.id == deadline_id, AssistantDeadline.student_id == student_id).with_for_update())
        if deadline is None or deadline.status in {"completed", "canceled"}:
            return "This deadline is no longer active."
        if action == "completed":
            deadline.status = "completed"
            db.execute(AssistantJob.__table__.update().where(
                AssistantJob.student_id == student_id, AssistantJob.deadline_id == deadline_id,
                AssistantJob.status.in_(["queued", "retry"])).values(status="canceled"))
            return "Deadline marked complete."
        if action == "acknowledged":
            deadline.confirmed_at = now
            return "Acknowledgment saved."
        if action in {"snooze", "tomorrow"}:
            if action == "tomorrow":
                try: zone = ZoneInfo(deadline.timezone_name)
                except (ZoneInfoNotFoundError, ValueError): zone = ZoneInfo("Asia/Kolkata")
                run_at = (datetime.now(zone) + timedelta(days=1)).astimezone(timezone.utc)
            else:
                if minutes is None or not 1 <= minutes <= 10080:
                    return "Choose a snooze from 1 minute to 7 days."
                run_at = now + timedelta(minutes=minutes)
            prefs = db.get(AssistantSettings, student_id)
            try: notifications = json.loads(prefs.notifications_json or "{}") if prefs else {}
            except (TypeError, ValueError): notifications = {}
            if not prefs or prefs.paused or not notifications.get("desktop_call", False):
                return "Reminder delivery is disabled in your preferences. No snooze was scheduled."
            key = f"livekit-snooze:{session_id}"
            existing = db.scalar(select(AssistantJob).where(
                AssistantJob.student_id == student_id, AssistantJob.idempotency_key == key))
            if existing and existing.status in {"queued", "retry"}:
                existing.run_at = run_at
            elif not existing:
                db.add(AssistantJob(id=new_id(), student_id=student_id, deadline_id=deadline.id,
                    kind="desktop_call", status="queued", run_at=run_at, idempotency_key=key,
                    attempts=0, max_attempts=5))
            return "Reminder rescheduled."
    return "No change was made."


@server.rtc_session(agent_name=get_settings().livekit_agent_name)
async def deadline_reminder_agent(ctx: JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    session_id = metadata.get("assistant_livekit_session_id")
    if not session_id:
        return
    values = await asyncio.to_thread(_read_context, session_id)
    if values is None:
        return
    student_id, deadline_id, title, due_at, zone_name, language, paused = values
    if paused:
        return
    with get_session_factory().begin() as db:
        row = db.get(AssistantLiveKitSession, session_id)
        if row: row.status = "active"

    async def apply(action: str, minutes: int | None = None) -> str:
        return await asyncio.to_thread(_apply_intent, student_id, deadline_id, session_id, action, minutes)

    @function_tool
    async def acknowledge(context: RunContext) -> str:
        return await apply("acknowledged")

    @function_tool
    async def mark_completed(context: RunContext) -> str:
        return await apply("completed")

    @function_tool
    async def snooze_reminder(context: RunContext, minutes: int) -> str:
        return await apply("snooze", minutes)

    @function_tool
    async def reschedule_for_tomorrow(context: RunContext) -> str:
        return await apply("tomorrow")

    def close():
        with get_session_factory().begin() as db:
            row = db.get(AssistantLiveKitSession, session_id)
            if row and row.status not in {"closed", "failed"}:
                row.status = "ended"; row.ended_at = datetime.now(timezone.utc)

    async def shutdown(*_): await asyncio.to_thread(close)

    try:
        zone = ZoneInfo(zone_name)
        due_display = due_at.astimezone(zone).strftime("%A, %B %d at %I:%M %p")
    except (ZoneInfoNotFoundError, ValueError): due_display = due_at.isoformat()
    spoken_language = {"te": "Telugu", "te-IN": "Telugu", "en": "English", "en-IN": "English",
                       "mixed": "natural Telugu-English code-switching"}.get(language, "Telugu and English")
    agent = Agent(instructions=(
        f"You are a concise and kind deadline reminder assistant. Speak in {spoken_language}. "
        f"The student's task is {title}, due {due_display}. Understand English and Telugu. "
        "If the student says they will do it, call acknowledge. Call mark_completed only when they explicitly say it is done. "
        "If they ask to be reminded later, ask how long when unclear and call snooze_reminder with minutes. "
        "For tomorrow, call reschedule_for_tomorrow. Wait for tool results; never claim an action succeeded if it failed."
    ), tools=[acknowledge, mark_completed, snooze_reminder, reschedule_for_tomorrow])
    language_mode = "te-IN" if language in {"te", "te-IN"} else "en-IN" if language in {"en", "en-IN"} else "mixed"
    output = agents.tts.StreamAdapter(tts=GnaniTimbreTTS(language=language_mode),
        sentence_tokenizer=tokenize.basic.SentenceTokenizer(language="telugu" if language_mode == "te-IN" else "english"))
    speech = stt.StreamAdapter(stt=GnaniPrismaSTT(), vad=silero.VAD.load())
    session = AgentSession(stt=speech,
        llm=google.LLM(model=get_settings().gemini_model, api_key=get_settings().gemini_api_key),
        tts=output, allow_interruptions=True, max_endpointing_delay=2.0)
    ctx.add_shutdown_callback(shutdown)
    await ctx.connect()
    await session.start(room=ctx.room, agent=agent)
    await session.generate_reply(instructions=f"Greet the student in {spoken_language}, remind them about {title} due {due_display}, and ask whether they want to acknowledge, complete, or snooze it.", input_modality="text")
