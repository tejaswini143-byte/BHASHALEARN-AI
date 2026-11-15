"""LiveKit Agents worker: REST turn-based Prisma/Timbre with Gemini conversation."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool, stt, tokenize
from livekit.plugins import google, silero
from sqlalchemy import select

from .db import SessionLocal
from .livekit_adapters import GnaniPrismaSTT, GnaniTimbreTTS
from .models import Deadline, Reminder, ReminderEvent, ReminderPreference, VoiceSession
from .settings import settings

server = AgentServer()


def _set_reminder(student_id: UUID, reminder_id: UUID, action: str, *, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        reminder = db.scalar(select(Reminder).where(Reminder.id == reminder_id, Reminder.student_id == student_id).with_for_update())
        if reminder is None:
            return "This reminder is no longer available."
        deadline = db.get(Deadline, reminder.deadline_id)
        if deadline is None or deadline.cancelled_at:
            return "This deadline has been cancelled."
        if action == "completed":
            reminder.status = "completed"
            deadline.completed_at = now
        elif action == "acknowledged":
            reminder.status = "acknowledged"
        elif action == "snooze":
            if minutes is None or not 1 <= minutes <= 10080:
                return "Please choose a snooze between 1 minute and 7 days."
            reminder.scheduled_at = now + timedelta(minutes=minutes)
            reminder.snoozed_until = reminder.scheduled_at
            reminder.status = "scheduled"
        elif action == "tomorrow":
            prefs = db.get(ReminderPreference, student_id)
            try:
                zone = ZoneInfo(prefs.timezone if prefs else deadline.timezone)
            except (ZoneInfoNotFoundError, ValueError):
                zone = ZoneInfo("Asia/Kolkata")
            reminder.scheduled_at = (datetime.now(zone) + timedelta(days=1)).astimezone(timezone.utc)
            reminder.snoozed_until = None
            reminder.status = "scheduled"
        db.add(ReminderEvent(reminder_id=reminder.id, event=action, detail="LiveKit Gemini tool action"))
        return f"Reminder {action} successfully."


def _session_context(session_id: UUID):
    with SessionLocal() as db:
        voice_session = db.get(VoiceSession, session_id)
        if not voice_session or voice_session.status not in {"creating", "dispatched", "active"}:
            return None
        reminder = db.get(Reminder, voice_session.reminder_id)
        if not reminder:
            return None
        deadline = db.get(Deadline, reminder.deadline_id)
        prefs = db.get(ReminderPreference, voice_session.student_id)
        return voice_session.student_id, reminder.id, deadline.title if deadline else "your deadline", deadline.due_at if deadline else None, prefs.timezone if prefs else "Asia/Kolkata", voice_session.language


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def deadline_reminder_agent(ctx: JobContext):
    metadata = json.loads(ctx.job.metadata or "{}")
    session_id = UUID(metadata["voice_session_id"])
    values = await asyncio.to_thread(_session_context, session_id)
    if values is None:
        return
    student_id, reminder_id, title, due_at, timezone_name, language = values
    with SessionLocal.begin() as db:
        voice_session = db.get(VoiceSession, session_id)
        if voice_session:
            voice_session.status = "active"
            if voice_session.reminder_id:
                db.add(ReminderEvent(reminder_id=voice_session.reminder_id, event="voice_session_active", detail=str(session_id)))

    async def close_session(*_args):
        def _close():
            with SessionLocal.begin() as db:
                row = db.get(VoiceSession, session_id)
                if row and row.status not in {"closed", "failed"}:
                    row.status = "ended"
                    row.ended_at = datetime.now(timezone.utc)
                    if row.reminder_id:
                        db.add(ReminderEvent(reminder_id=row.reminder_id, event="voice_session_ended", detail=str(session_id)))
        await asyncio.to_thread(_close)

    @function_tool
    async def mark_acknowledged(context: RunContext) -> str:
        return await asyncio.to_thread(_set_reminder, student_id, reminder_id, "acknowledged")

    @function_tool
    async def mark_completed(context: RunContext) -> str:
        return await asyncio.to_thread(_set_reminder, student_id, reminder_id, "completed")

    @function_tool
    async def snooze_reminder(context: RunContext, minutes: int) -> str:
        return await asyncio.to_thread(_set_reminder, student_id, reminder_id, "snooze", minutes=minutes)

    @function_tool
    async def reschedule_for_tomorrow(context: RunContext) -> str:
        return await asyncio.to_thread(_set_reminder, student_id, reminder_id, "tomorrow")

    language_name = {"te-IN": "Telugu", "en-IN": "English", "mixed": "natural Telugu-English code-switching"}.get(language, "Telugu and English")
    due_text = ""
    if due_at:
        try:
            due_text = f" Due {due_at.astimezone(ZoneInfo(timezone_name)).strftime('%A, %B %d at %I:%M %p')}."
        except (ZoneInfoNotFoundError, ValueError):
            due_text = f" Due {due_at.isoformat()}."
    instructions = (
        f"You are a warm, concise deadline reminder assistant. Speak in {language_name}. "
        f"The student's task is: {title}.{due_text} Understand English and Telugu. "
        "When the student says they will do it, call mark_acknowledged. "
        "Only call mark_completed after an explicit statement that the task is already done. "
        "When asked to remind later, ask how long if unspecified, then call snooze_reminder with minutes. "
        "For tomorrow, call reschedule_for_tomorrow. Wait for each tool result before confirming an action. "
        "Never claim an action succeeded if a tool reports otherwise."
    )
    agent = Agent(instructions=instructions, tools=[mark_acknowledged, mark_completed, snooze_reminder, reschedule_for_tomorrow])
    tts_adapter = GnaniTimbreTTS(language=language)
    tts_stream = agents.tts.StreamAdapter(tts=tts_adapter, sentence_tokenizer=tokenize.basic.SentenceTokenizer(
        language="telugu" if language == "te-IN" else "english"))
    stt_adapter = stt.StreamAdapter(stt=GnaniPrismaSTT(), vad=silero.VAD.load())
    session = AgentSession(stt=stt_adapter, llm=google.LLM(model=settings.gemini_model, api_key=settings.gemini_api_key), tts=tts_stream,
                           allow_interruptions=True, max_endpointing_delay=2.0)
    ctx.add_shutdown_callback(close_session)
    await ctx.connect()
    await session.start(room=ctx.room, agent=agent)
    greeting = f"Hello! This is your reminder for {title}.{due_text} Would you like to acknowledge it, mark it complete, or snooze it?"
    await session.generate_reply(instructions=greeting, input_modality="text")


if __name__ == "__main__":
    cli.run_app(server)
