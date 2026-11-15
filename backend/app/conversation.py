"""Provider orchestration for one browser reminder turn."""
from google import genai
from google.genai import types
from .settings import settings


def interpret_turn(transcript: str, title: str, language: str) -> tuple[str, str, int | None]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = f"""You are a concise, kind Telugu-English deadline reminder assistant. Reply in {language}.
Deadline: {title}
Student said: {transcript}
Return exactly JSON with keys intent (acknowledged|completed|snooze|reschedule|clarify), reply (natural spoken response), minutes (integer or null).
Only use completed when the student explicitly says the work is done. For tomorrow, use reschedule and ask a time if none is specified. Never claim an action succeeded unless its intent is valid."""
    response = client.models.generate_content(model=settings.gemini_model, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
    import json
    data = json.loads(response.text or "{}")
    intent = data.get("intent")
    if intent not in {"acknowledged", "completed", "snooze", "reschedule", "clarify"}:
        raise RuntimeError("Gemini returned an unsupported reminder action")
    minutes = data.get("minutes")
    if minutes is not None and (not isinstance(minutes, int) or not 1 <= minutes <= 10080):
        minutes = None
    return intent, str(data.get("reply", ""))[:500], minutes

