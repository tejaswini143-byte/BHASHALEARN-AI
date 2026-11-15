"""REST bridge for current Gnani POC adapters; this is turn-based, not streaming."""
from dataclasses import dataclass
from pathlib import Path
import sys

POC = Path(__file__).resolve().parents[2] / "pocs"
sys.path.insert(0, str(POC / "poc01_prisma_stt"))
sys.path.insert(0, str(POC / "poc02_timbre_tts"))


@dataclass
class TurnResult:
    transcript: str
    reply: str
    audio: bytes | None
    provider_status: dict[str, str]


def response_for(transcript: str, language: str, deadline_title: str) -> tuple[str, str | None, str | None]:
    """Deterministic safe intents for demo fallback; completion requires explicit language."""
    normalized = transcript.casefold()
    if any(x in normalized for x in ("already completed", "completed it", "పూర్తి చేశాను", "పూర్తయింది")):
        return "completed", "Great, I marked it completed.", None
    if any(x in normalized for x in ("30 minutes", "half an hour", "30 నిమిషాలు")):
        return "snooze", "Okay, I will remind you again in 30 minutes.", None
    if any(x in normalized for x in ("tomorrow", "రేపు")):
        return "reschedule", "Okay, I will move the reminder to tomorrow. What time works for you?", None
    if any(x in normalized for x in ("okay", "i will submit", "సరే", "చేస్తాను")):
        return "acknowledged", f"Okay. I’ll remind you about {deadline_title} again if needed.", None
    return "clarify", f"Your deadline is {deadline_title}. Would you like to acknowledge, complete, or snooze it?", None

