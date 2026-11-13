"""Opt-in, loopback-only Windows mouse companion for the local QA page."""
from __future__ import annotations

import json
import os
import secrets
import ctypes
import threading
import time
import io
import wave
from uuid import uuid4
from datetime import datetime, timezone
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
import winsound
import tkinter as tk
from tkinter import ttk
try:
    import sounddevice as sd
except ImportError:  # The incoming-call window still works without local audio capture.
    sd = None

import pyautogui
import pygetwindow
try:
    from . import windows_automation
except ImportError:  # Direct script entry point: scripts/ is sys.path[0].
    import windows_automation

HOST, PORT = "127.0.0.1", int(os.getenv("BHASHALEARN_COMPANION_PORT", "18765"))
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:5200", "http://localhost:5200", "http://127.0.0.1:5201", "http://localhost:5201", "http://127.0.0.1:5202", "http://localhost:5202", "http://127.0.0.1:5203", "http://localhost:5203", "http://127.0.0.1:15199", "http://localhost:15199", "http://127.0.0.1:5199", "http://localhost:5199", "http://127.0.0.1:5198", "http://localhost:5198", "http://127.0.0.1:5210", "http://localhost:5210", "http://127.0.0.1:5211", "http://localhost:5211"}
ALLOWED_API_PORTS = {8027, 18027, 18029, 18030, 18031, 18034, 5198, 5199, 5200, 5201, 5202, 5203, 5210, 5211, 5173}
TOKEN = os.getenv("BHASHALEARN_COMPANION_TOKEN") or secrets.token_urlsafe(32)
SHOW_PAIRING_TOKEN = os.getenv("BHASHALEARN_SHOW_COMPANION_TOKEN", "").casefold() == "true"
lock = threading.Lock()
active = False
stopped = False
last_action = ""
last_at = 0.0
background_lock = threading.Lock()
background_config: dict[str, str] = {}
background_stop = threading.Event()
desktop_stop = threading.Event()
confirmation_lock = threading.Lock()
pending_execution_confirmations: dict[str, tuple[float, str]] = {}
call_ui_root = None
call_windows: dict[str, dict] = {}
call_windows_lock = threading.Lock()
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.15


def _confirmation_fingerprint(payload: dict) -> str:
    relevant = {key: payload.get(key) for key in (
        "action", "snapshot_id", "active_window_id", "focus_target_id", "confirmed_close")}
    return json.dumps(relevant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_native_execution_approval(action: dict) -> bool:
    """Fail closed unless the local Windows operator approves the exact action.

    Browser-origin requests and a bearer token do not prove a human clicked
    the web confirmation button. A separate native prompt is required.
    """
    if os.name != "nt":
        return False
    import ctypes
    action_name = str(action.get("action", "unknown"))[:80]
    app_name = str(action.get("app_id") or action.get("target_name") or "")[:80]
    detail = f"{action_name}: {app_name}" if app_name else action_name
    message = ("BHASHALEARN AI requests a Windows desktop action:\\n\\n"
               + detail + "\\n\\nApprove this action? Choose No to cancel.")
    # MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2 | MB_TOPMOST
    return ctypes.windll.user32.MessageBoxW(None, message, "BHASHALEARN AI — Desktop approval",
                                             0x00000004 | 0x00000030 | 0x00000100 | 0x00040000) == 6


def _clear_execution_confirmations() -> None:
    with confirmation_lock:
        pending_execution_confirmations.clear()

QA_WINDOW_TITLE = "BHASHALEARN Desktop Control QA"
WINDOW_PADDING = 24
TEST_TARGET_WIDTH_RATIO = 0.40


def active_qa_bounds() -> tuple[int, int, int, int]:
    """Require the disposable QA page to be the foreground window."""
    window = pygetwindow.getActiveWindow()
    if window is None or QA_WINDOW_TITLE.casefold() not in (window.title or "").casefold():
        raise RuntimeError("Bring the BHASHALEARN Desktop Control QA page to the foreground first")
    left, top, width, height = int(window.left), int(window.top), int(window.width), int(window.height)
    if width <= WINDOW_PADDING * 2 or height <= WINDOW_PADDING * 2:
        raise RuntimeError("QA browser window is too small for bounded control")
    return left + WINDOW_PADDING, top + WINDOW_PADDING, width - WINDOW_PADDING * 2, height - WINDOW_PADDING * 2


def type_text(text: str) -> None:
    """Type Unicode through Windows keyboard events without replacing clipboard data."""
    if text.isascii():
        pyautogui.write(text, interval=0.015)
        return
    if os.name != "nt":
        raise RuntimeError("Unicode desktop typing requires Windows")

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("union", INPUTUNION)]

    send_input = ctypes.windll.user32.SendInput
    encoded = text.encode("utf-16-le")
    code_units = [int.from_bytes(encoded[index:index + 2], "little")
                  for index in range(0, len(encoded), 2)]
    for code_unit in code_units:
        for flags in (0x0004, 0x0004 | 0x0002):  # KEYEVENTF_UNICODE, then KEYUP
            event = INPUT(1, INPUTUNION(KEYBDINPUT(0, code_unit, flags, 0, None)))
            if send_input(1, ctypes.byref(event), ctypes.sizeof(INPUT)) != 1:
                raise RuntimeError("Windows rejected Unicode keyboard input")


def _background_request(method: str, path: str, *, payload=None, audio_bytes: bytes | None = None):
    with background_lock:
        cfg = dict(background_config)
    if not cfg.get("api_base") or not cfg.get("access_token"):
        raise RuntimeError("Connect an authenticated student session from BHASHALEARN first")
    url = cfg["api_base"].rstrip("/") + path
    headers = {"Authorization": "Bearer " + cfg["access_token"], "X-Request-ID": str(uuid4())}
    try:
        with httpx.Client(timeout=20.0) as client:
            if audio_bytes is not None:
                response = client.post(url, headers=headers,
                    files={"audio": ("deadline-call.wav", audio_bytes, "audio/wav")},
                    data=payload or {})
            elif method == "GET":
                response = client.get(url, headers=headers)
            else:
                response = client.post(url, headers=headers, json=payload or {})
        if not response.is_success:
            if response.status_code == 401:
                raise RuntimeError("The student session expired. Reconnect this companion from BHASHALEARN.")
            detail = response.json().get("detail", "The local call request failed.")
            raise RuntimeError(str(detail)[:240])
        return response.json() if "application/json" in response.headers.get("content-type", "") else response.content
    except httpx.HTTPError as exc:
        raise RuntimeError("The local BHASHALEARN service is unavailable.") from exc


def _play_speech(text: str, language: str):
    speech = _background_request("POST", "/assistant/voice/speech",
        payload={"text": text[:3000], "language": language if language in {"en", "te", "mixed"} else "mixed"})
    if not isinstance(speech, bytes) or not speech:
        raise RuntimeError("Timbre did not return audio.")
    winsound.PlaySound(speech, winsound.SND_MEMORY)


def _capture_wav(seconds: int = 7) -> bytes:
    if sd is None:
        raise RuntimeError("Install the companion audio dependencies to use its microphone.")
    samplerate = 16000
    recording = sd.rec(int(samplerate * seconds), samplerate=samplerate, channels=1, dtype="int16")
    sd.wait()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(samplerate)
        wav.writeframes(recording.tobytes())
    return output.getvalue()


def _set_call_status(call_id: str, status_text: str):
    with call_windows_lock:
        data = call_windows.get(call_id)
    if data and call_ui_root:
        def update():
            try:
                if data["status"].winfo_exists():
                    data["status"].configure(text=status_text)
            except tk.TclError:
                pass
        try:
            call_ui_root.after(0, update)
        except tk.TclError:
            pass


def _schedule_call_ui(data: dict, callback):
    try:
        data["root"].after(0, callback)
    except tk.TclError:
        pass


def _begin_voice_turn(call: dict, data: dict, *, interrupt: bool = False):
    """Prevent echo capture while speaking; permit one explicit barge-in."""
    if data.get("listening") or (interrupt and not data.get("speaking")):
        return
    if not interrupt and data.get("speaking"):
        return
    if interrupt:
        winsound.PlaySound(None, winsound.SND_PURGE)
        data["speaking"] = False
    data["interrupt_requested"] = interrupt
    data["listening"] = True
    data["speak"].configure(state="disabled")
    data["interrupt"].configure(state="disabled")
    threading.Thread(target=_voice_turn, args=(call, data), daemon=True).start()


def _speak_async(call_id: str, text: str, language: str):
    try:
        _set_call_status(call_id, "SPEAKING · BHASHALEARN AI")
        _play_speech(text, language)
    except Exception as exc:
        _set_call_status(call_id, "Speech unavailable: " + str(exc))
    else:
        _set_call_status(call_id, "LISTENING · choose Speak when ready")


def _answer_call(call: dict, data: dict):
    call_id = call["id"]
    try:
        result = _background_request("POST", "/assistant/local-calls/" + call_id + "/answer",
            payload={"explicit_user_action": True, "initiating_component": "windows_answer_button"})
        greeting = result.get("greeting", "")
        duration_minutes = max(5, min(120, int(result.get("max_duration_minutes", call.get("max_duration_minutes", 30)))))
        call["max_duration_minutes"] = duration_minutes
        data["speaking"] = bool(greeting)
        def show_answered():
            try:
                if not data["window"].winfo_exists():
                    return
                data["status"].configure(text="SPEAKING · BHASHALEARN AI" if greeting else "LISTENING · ready")
                data["title"].configure(text=call.get("title", "Deadline reminder"))
                data["answer"].pack_forget(); data["snooze"].pack_forget(); data["dismiss"].pack_forget()
                data["speak"].pack(side="left", padx=4); data["interrupt"].pack(side="left", padx=4)
                data["retry"].pack(side="left", padx=4)
                data["extend"].pack(side="left", padx=4); data["end"].pack(side="left", padx=4)
                data["speak"].configure(state="disabled" if greeting else "normal")
                data["interrupt"].configure(state="disabled")
            except tk.TclError:
                pass
        data["root"].after(0, show_answered)
        _arm_duration_timer(call, data, result.get("answered_at"), duration_minutes)
        if greeting:
            shown_greeting = greeting if len(greeting) <= 300 else greeting[:297] + "..."
            data["root"].after(0, lambda: data["reply"].winfo_exists() and data["reply"].configure(text=shown_greeting))
            _play_speech(greeting, result.get("language", call.get("language", "en")))
        data["speaking"] = False
        _set_call_status(call_id, "LISTENING · choose Speak when ready")
        _schedule_call_ui(data, lambda: data["speak"].winfo_exists() and data["speak"].configure(state="normal"))
    except Exception as exc:
        error = str(exc)
        data["speaking"] = False
        _schedule_call_ui(data, lambda error=error: (
            data["status"].winfo_exists() and data["status"].configure(text="Answer failed: " + error),
            data["answer"].winfo_exists() and data["answer"].configure(state="normal")))


def _duration_expired(call: dict, data: dict, duration_minutes: int):
    _set_call_status(call["id"], f"ENDED · {duration_minutes}-minute limit reached")
    _finish_call(call, "end", data)


def _arm_duration_timer(call: dict, data: dict, answered_at: str | None, duration_minutes: int):
    if not answered_at:
        remaining_ms = duration_minutes * 60_000
    else:
        parsed = datetime.fromisoformat(answered_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        remaining_ms = max(1, int((parsed.timestamp() + duration_minutes * 60 - time.time()) * 1000))
    old_timer = data.pop("duration_timer", None)
    if old_timer:
        try: data["root"].after_cancel(old_timer)
        except tk.TclError: pass
    data["duration_timer"] = data["root"].after(remaining_ms,
        lambda: _duration_expired(call, data, duration_minutes))


def _extend_call(call: dict, data: dict, additional_minutes: int = 10):
    try:
        result = _background_request("POST", "/assistant/local-calls/" + call["id"] + "/extend",
            payload={"additional_minutes": additional_minutes})
        call["max_duration_minutes"] = result["max_duration_minutes"]
        def update_duration():
            _arm_duration_timer(call, data, result.get("answered_at"), result["max_duration_minutes"])
            if data["status"].winfo_exists():
                data["status"].configure(text=f"LISTENING · limit extended to {result['max_duration_minutes']} minutes")
        _schedule_call_ui(data, update_duration)
    except Exception as exc:
        _set_call_status(call["id"], "Could not extend call: " + str(exc))


def _voice_turn(call: dict, data: dict):
    call_id = call["id"]
    try:
        authorization = _background_request("POST", "/assistant/local-calls/" + call_id + "/microphone",
            payload={"explicit_user_action": True, "initiating_component":
                     "windows_interrupt_button" if data.get("interrupt_requested") else "windows_speak_button"})
        _set_call_status(call_id, "LISTENING · recording a short turn")
        audio_bytes = _capture_wav()
        transcript = _background_request("POST", "/assistant/local-calls/" + call_id + "/transcribe",
            audio_bytes=audio_bytes, payload={"microphone_authorization": authorization["authorization"]})
        text = transcript.get("transcript", "").strip() if isinstance(transcript, dict) else ""
        if not text:
            raise RuntimeError("Prisma returned an empty transcript; try again.")
        shown_transcript = text if len(text) <= 240 else text[:237] + "..."
        data["root"].after(0, lambda: data["transcript"].winfo_exists() and data["transcript"].configure(text=shown_transcript))
        data["listening"] = False
        data["retry_turn"] = {"text": text[:2000], "turn_id": str(uuid4())}
        _submit_local_turn(call, data, data["retry_turn"])
    except Exception as exc:
        data["speaking"] = False
        data["listening"] = False
        _schedule_call_ui(data, lambda: (
            data["speak"].winfo_exists() and data["speak"].configure(state="normal"),
            data["interrupt"].winfo_exists() and data["interrupt"].configure(state="disabled"),
            data.get("retry") and data["retry"].winfo_exists() and data["retry"].configure(
                state="normal" if data.get("retry_turn") else "disabled")))
        _set_call_status(call_id, "Call error: " + str(exc))
    finally:
        data["listening"] = False
        if not data.get("speaking"):
            _schedule_call_ui(data, lambda: (
                data["speak"].winfo_exists() and data["speak"].configure(state="normal"),
                data["interrupt"].winfo_exists() and data["interrupt"].configure(state="disabled")))


def _submit_local_turn(call: dict, data: dict, turn: dict):
    call_id = call["id"]
    try:
        result = _background_request("POST", "/assistant/local-calls/" + call_id + "/turn",
            payload={"text": turn["text"], "language": call.get("language", "mixed"),
                     "turn_id": turn["turn_id"]})
    except Exception as exc:
        data["speaking"] = False
        data["listening"] = False
        _schedule_call_ui(data, lambda: data["retry"].winfo_exists() and data["retry"].configure(state="normal"))
        _set_call_status(call_id, "AI turn failed · press Retry turn: " + str(exc)[:120])
        return

    data["retry_turn"] = None
    _schedule_call_ui(data, lambda: data["retry"].winfo_exists() and data["retry"].configure(state="disabled"))
    reply = result.get("reply", "")
    shown_reply = reply if len(reply) <= 300 else reply[:297] + "..."
    data["speaking"] = True
    _set_call_status(call_id, "SPEAKING · BHASHALEARN AI")
    _schedule_call_ui(data, lambda: (
        data["reply"].winfo_exists() and data["reply"].configure(text=shown_reply),
        data["speak"].winfo_exists() and data["speak"].configure(state="disabled"),
        data["interrupt"].winfo_exists() and data["interrupt"].configure(state="normal")))
    try:
        _play_speech(reply, result.get("language", call.get("language", "mixed")))
    except Exception as exc:
        _set_call_status(call_id, "Timbre speech unavailable: " + str(exc)[:120])
    else:
        proposal = result.get("proposed_reminder_at")
        if proposal:
            data["pending_reminder_at"] = proposal
            data["root"].after(0, lambda: data["reschedule"].configure(state="normal", text="Confirm reminder at " + proposal[:16]))
            _set_call_status(call_id, "THINKING · reminder needs your confirmation")
        else:
            _set_call_status(call_id, "LISTENING · choose Speak when ready")
    finally:
        data["speaking"] = False
        _schedule_call_ui(data, lambda: (
            data["speak"].winfo_exists() and data["speak"].configure(state="normal"),
            data["interrupt"].winfo_exists() and data["interrupt"].configure(state="disabled")))


def _retry_local_turn(call: dict, data: dict):
    turn = data.get("retry_turn")
    if not turn:
        return
    data["retry"].configure(state="disabled")
    threading.Thread(target=_submit_local_turn, args=(call, data, turn), daemon=True).start()


def _finish_call(call: dict, action: str, data: dict):
    try:
        timer = data.pop("duration_timer", None)
        if timer:
            try: data["root"].after_cancel(timer)
            except tk.TclError: pass
        winsound.PlaySound(None, winsound.SND_PURGE)
        _background_request("POST", "/assistant/local-calls/" + call["id"] + "/" + action,
            payload={"minutes": 10} if action == "snooze" else {})
        with call_windows_lock:
            call_windows.pop(call["id"], None)
        data["root"].after(0, lambda: data["window"].winfo_exists() and data["window"].destroy())
    except Exception as exc:
        _set_call_status(call["id"], "Call action failed: " + str(exc))


def _confirm_local_reschedule(call: dict, data: dict):
    try:
        reminder_at = data.get("pending_reminder_at")
        if not reminder_at:
            return
        path = "/assistant/local-calls/" + call["id"] + "/reschedule"
        payload = {"reminder_at": reminder_at, "confirmed": False}
        _background_request("POST", path, payload=payload)
        payload["confirmed"] = True
        _background_request("POST", path, payload=payload)
        data["root"].after(0, lambda: data["reschedule"].winfo_exists() and data["reschedule"].configure(text="Reminder scheduled", state="disabled"))
        _set_call_status(call["id"], "LISTENING · reminder scheduled")
    except Exception as exc:
        _set_call_status(call["id"], "Reschedule failed: " + str(exc))


def _show_incoming_call(call: dict):
    call_id = call.get("id")
    if not call_id or not call_ui_root:
        return
    with call_windows_lock:
        if call_id in call_windows:
            return
        # Reserve before scheduling the Tk callback. The polling thread can
        # deliver the same ringing call repeatedly before Tk processes it.
        call_windows[call_id] = {"creating": True}

    def create_window():
        with call_windows_lock:
            entry = call_windows.get(call_id)
            if not entry or not entry.get("creating"):
                return
            entry["creating"] = False
        try:
            window = tk.Toplevel(call_ui_root)
        except Exception:
            with call_windows_lock:
                call_windows.pop(call_id, None)
            return
        window.title("BHASHALEARN AI — Deadline Call")
        window.geometry("440x420+80+80")
        window.minsize(440, 420)
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", lambda: _finish_call(call, "dismiss", data))
        frame = ttk.Frame(window, padding=18); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="BHASHALEARN AI", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        title = ttk.Label(frame, text=call.get("title", "Deadline reminder"), wraplength=390, font=("Segoe UI", 12))
        title.pack(anchor="w", pady=(8, 4))
        status = ttk.Label(frame, text="RINGING · local Windows reminder"); status.pack(anchor="w")
        transcript = ttk.Label(frame, text="", wraplength=390); transcript.pack(anchor="w", pady=(8, 2))
        reply = ttk.Label(frame, text="", wraplength=390); reply.pack(anchor="w", pady=(3, 8))
        actions = ttk.Frame(frame); actions.pack(fill="x", pady=6)
        data = {"root": call_ui_root, "window": window, "status": status, "title": title, "call": call,
                "transcript": transcript, "reply": reply, "pending_reminder_at": None,
                "speaking": False, "listening": False}
        answer = ttk.Button(actions, text="Answer")
        def begin_answer():
            if str(answer.cget("state")) == "disabled":
                return
            answer.configure(state="disabled")
            status.configure(text="ANSWERING · BHASHALEARN AI")
            threading.Thread(target=_answer_call, args=(call, data), daemon=True).start()
        answer.configure(command=begin_answer)
        snooze = ttk.Button(actions, text="Snooze 10 min", command=lambda: threading.Thread(target=_finish_call,
            args=(call, "snooze", data), daemon=True).start(), state="normal" if call.get("deadline_id") else "disabled")
        dismiss = ttk.Button(actions, text="Dismiss", command=lambda: threading.Thread(target=_finish_call,
            args=(call, "dismiss", data), daemon=True).start())
        speak_button = ttk.Button(actions, text="Speak")
        interrupt = ttk.Button(actions, text="Interrupt & speak", state="disabled")
        retry = ttk.Button(actions, text="Retry turn", state="disabled",
            command=lambda: _retry_local_turn(call, data))
        end = ttk.Button(actions, text="End call", command=lambda: threading.Thread(target=_finish_call,
            args=(call, "end", data), daemon=True).start())
        extend = ttk.Button(actions, text="Extend +10 min", command=lambda: threading.Thread(target=_extend_call,
            args=(call, data, 10), daemon=True).start())
        reschedule = ttk.Button(frame, text="Confirm reminder", state="disabled",
            command=lambda: threading.Thread(target=_confirm_local_reschedule, args=(call, data), daemon=True).start())
        answer.pack(side="left", padx=4); snooze.pack(side="left", padx=4); dismiss.pack(side="left", padx=4)
        reschedule.pack(anchor="w", pady=4)
        data.update(answer=answer, snooze=snooze, dismiss=dismiss, speak=speak_button,
                    interrupt=interrupt, retry=retry, end=end, extend=extend, reschedule=reschedule)
        speak_button.configure(command=lambda: _begin_voice_turn(call, data))
        interrupt.configure(command=lambda: _begin_voice_turn(call, data, interrupt=True))
        with call_windows_lock:
            call_windows[call_id] = data

        def ring_once():
            with call_windows_lock:
                active_window = call_windows.get(call_id)
            if active_window is None or not active_window["window"].winfo_exists():
                return
            if active_window["status"].cget("text").startswith("RINGING"):
                try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
                except RuntimeError: pass
                call_ui_root.after(1300, ring_once)
        ring_once()

    call_ui_root.after(0, create_window)


def _background_poll():
    while not background_stop.wait(5):
        with background_lock:
            configured = bool(background_config.get("api_base") and background_config.get("access_token"))
        if not configured:
            continue
        try:
            pending = _background_request("GET", "/assistant/local-calls/pending")
            for call in pending if isinstance(pending, list) else []:
                _show_incoming_call(call)
        except Exception as exc:
            # Keep the companion alive through transient API or network errors.
            last_action = "Reminder connection unavailable: " + str(exc)[:120]


def _call_ui_mainloop():
    global call_ui_root
    try:
        call_ui_root = tk.Tk()
        call_ui_root.withdraw()
        call_ui_root.mainloop()
    except Exception:
        call_ui_root = None


def _end_calls_on_shutdown():
    """Persist a clean terminal state for calls displayed by this companion."""
    with call_windows_lock:
        entries = list(call_windows.items())
    for call_id, data in entries:
        call = data.get("call") if isinstance(data, dict) else None
        if not isinstance(call, dict):
            continue
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
            _background_request("POST", "/assistant/local-calls/" + call_id + "/end")
        except Exception:
            # Shutdown must still release the UI and server if the API is down.
            pass
        finally:
            data["speaking"] = False
            data["listening"] = False
    with call_windows_lock:
        call_windows.clear()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers(); self.wfile.write(data)

    def log_message(self, *_): pass

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            return self._send(403, {"error": "origin not allowed"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def _auth(self):
        import hmac
        return hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {TOKEN}")

    def do_GET(self):
        if self.path == "/pair":
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                return self._send(403, {"error": "pairing is available only to the local BHASHALEARN app"})
            self._send(200, {"token": TOKEN, "loopback_only": True})
            return
        if self.path not in {"/health", "/desktop/snapshot"}: return self._send(404, {"error": "not found"})
        if not self._auth(): return self._send(401, {"error": "unauthorized"})
        if self.path == "/desktop/snapshot":
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                return self._send(403, {"error": "desktop snapshots are available only to the local BHASHALEARN app"})
            try:
                self._send(200, windows_automation.get_snapshot())
            except Exception as exc:
                self._send(503, {"error": "Windows UI Automation snapshot failed: " + str(exc)[:180]})
            return
        if self.path != "/health": return self._send(404, {"error": "not found"})
        with background_lock:
            background_enabled = bool(background_config.get("api_base") and background_config.get("access_token"))
        self._send(200, {"connected": True, "active": active, "stopped": stopped,
                         "background_reminders": background_enabled, "last_action": last_action})

    def do_POST(self):
        global active, stopped, last_action, last_at
        if not self._auth(): return self._send(401, {"error": "unauthorized"})
        if self.path in {"/background/enable", "/background/disable"}:
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                return self._send(403, {"error": "background reminders are available only to the local BHASHALEARN app"})
            length = min(int(self.headers.get("Content-Length", "0")), 4096)
            try: data = json.loads(self.rfile.read(length))
            except Exception: return self._send(400, {"error": "invalid JSON"})
            if self.path == "/background/disable":
                with background_lock:
                    background_config.clear()
                return self._send(200, {"enabled": False})
            if not isinstance(data, dict): return self._send(400, {"error": "invalid session configuration"})
            api_base = data.get("api_base"); access_token = data.get("access_token")
            try:
                parsed = urlparse(api_base)
                if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}
                        or parsed.port not in ALLOWED_API_PORTS or parsed.path != "/api/v1"
                        or parsed.query or parsed.fragment or not isinstance(access_token, str)
                        or not 20 <= len(access_token) <= 4096):
                    raise ValueError("Only an authenticated loopback BHASHALEARN API session is accepted")
                check = httpx.get(api_base + "/auth/me", headers={"Authorization": "Bearer " + access_token}, timeout=5.0)
                if check.status_code != 200:
                    raise ValueError("The BHASHALEARN student session is invalid or expired")
            except (ValueError, TypeError, httpx.HTTPError) as exc:
                return self._send(422, {"error": str(exc)[:240]})
            with background_lock:
                background_config["api_base"] = api_base
                background_config["access_token"] = access_token
            background_stop.clear()
            if not any(t.name == "bhashalearn-local-reminders" and t.is_alive() for t in threading.enumerate()):
                threading.Thread(target=_background_poll, name="bhashalearn-local-reminders", daemon=True).start()
            return self._send(200, {"enabled": True, "delivery": "loopback_companion"})
        if self.path not in {"/activate", "/disable", "/stop", "/action", "/desktop/confirm", "/desktop/execute"}:
            return self._send(404, {"error": "not found"})
        if self.path == "/stop":
            with lock: active = False; stopped = True; desktop_stop.set()
            _clear_execution_confirmations()
            last_action = "Emergency stop; desktop control disabled"
            return self._send(200, {"ok": True, "active": False, "last_action": last_action})
        if self.path == "/disable":
            with lock: active = False; desktop_stop.set()
            _clear_execution_confirmations()
            return self._send(200, {"ok": True, "active": False})
        if self.path == "/activate":
            with lock: active = True; stopped = False; desktop_stop.clear()
            _clear_execution_confirmations()
            return self._send(200, {"ok": True, "active": True})
        if not active or stopped: return self._send(423, {"error": "desktop control is disabled"})
        if self.path in {"/desktop/confirm", "/desktop/execute"}:
            if self.headers.get("Origin") not in ALLOWED_ORIGINS:
                return self._send(403, {"error": "desktop approval is available only to the local BHASHALEARN app"})
            length = min(int(self.headers.get("Content-Length", "0")), 8192)
            try: payload = json.loads(self.rfile.read(length))
            except Exception: return self._send(400, {"error": "invalid JSON"})
            if not isinstance(payload, dict) or not isinstance(payload.get("action"), dict):
                return self._send(422, {"error": "a validated action plan is required"})
            if self.path == "/desktop/confirm":
                # Independent OS-level consent: an authenticated browser request
                # alone must never mint an executable confirmation ticket.
                if not _require_native_execution_approval(payload["action"]):
                    return self._send(403, {"error": "local Windows operator did not approve this action"})
                if not active or stopped or desktop_stop.is_set():
                    return self._send(423, {"error": "desktop control was stopped during approval"})
                confirmation = secrets.token_urlsafe(32)
                fingerprint = _confirmation_fingerprint(payload)
                with confirmation_lock:
                    now = time.monotonic()
                    for key, (expires, _) in list(pending_execution_confirmations.items()):
                        if expires <= now: pending_execution_confirmations.pop(key, None)
                    pending_execution_confirmations[confirmation] = (now + 60.0, fingerprint)
                return self._send(200, {"confirmation_token": confirmation, "expires_in_seconds": 60})
            confirmation = payload.get("confirmation_token")
            with confirmation_lock:
                pending = pending_execution_confirmations.pop(confirmation, None) if isinstance(confirmation, str) else None
            if not pending or pending[0] <= time.monotonic() or pending[1] != _confirmation_fingerprint(payload):
                return self._send(409, {"error": "a fresh one-time user confirmation is required for this exact action"})
            def ensure_control_active():
                if desktop_stop.is_set() or not active or stopped:
                    raise RuntimeError("Emergency Stop cancelled the remaining desktop actions.")
            try:
                result = windows_automation.execute_action(
                    payload["action"], snapshot_id=payload.get("snapshot_id"),
                    active_window_id=payload.get("active_window_id"),
                    focus_target_id=payload.get("focus_target_id"),
                    confirmed_close=payload.get("confirmed_close") is True,
                    type_text=type_text, cancel_check=ensure_control_active)
            except pyautogui.FailSafeException:
                with lock: active = False; stopped = True; desktop_stop.set()
                return self._send(423, {"error": "PyAutoGUI fail-safe stopped desktop control"})
            except Exception as exc:
                return self._send(422, {"error": str(exc)[:240]})
            last_at = time.monotonic()
            last_action = str(payload["action"].get("action", "sequence"))
            return self._send(200, result)
        if time.monotonic() - last_at < 0.25: return self._send(429, {"error": "command rate limited"})
        length = min(int(self.headers.get("Content-Length", "0")), 2048)
        try: data = json.loads(self.rfile.read(length))
        except Exception: return self._send(400, {"error": "invalid JSON"})
        action = data.get("action") if isinstance(data, dict) else None
        try:
            left, top, width, height = active_qa_bounds()
        except RuntimeError as exc:
            return self._send(423, {"error": str(exc)})
        x, y = pyautogui.position()
        start_x, start_y = x, y
        inside = left <= x < left + width and top <= y < top + height
        target_right = left + int(width * TEST_TARGET_WIDTH_RATIO)
        in_test_area = left <= x < target_right and top <= y < top + height
        if action in {"click", "double_click", "scroll_up", "scroll_down", "type", "enter"} and not in_test_area:
            return self._send(423, {"error": "Move the pointer inside the disposable test-control column before this action"})
        try:
            if action == "center": x, y = left + min(width // 2, int(width * TEST_TARGET_WIDTH_RATIO) // 2), top + height // 2; pyautogui.moveTo(x, y, 0.2)
            elif action == "move_to":
                target_x, target_y = data.get("x"), data.get("y")
                if isinstance(target_x, bool) or isinstance(target_y, bool) or not isinstance(target_x, int) or not isinstance(target_y, int):
                    return self._send(422, {"error": "move_to requires integer screen coordinates"})
                if not (left <= target_x < target_right and top <= target_y < top + height):
                    return self._send(423, {"error": "Target is outside the bounded disposable test-control column"})
                x, y = target_x, target_y
                pyautogui.moveTo(x, y, 0.2)
            elif action in {"left", "right", "up", "down"}:
                dx, dy = {"left":(-80,0), "right":(80,0), "up":(0,-80), "down":(0,80)}[action]
                x, y = max(left,min(left+width-1,x+dx)), max(top,min(top+height-1,y+dy)); pyautogui.moveTo(x,y,0.15)
            elif action == "click": pyautogui.click()
            elif action == "double_click": pyautogui.doubleClick()
            elif action == "scroll_down": pyautogui.scroll(-4)
            elif action == "scroll_up": pyautogui.scroll(4)
            elif action == "type":
                text = data.get("text")
                if not isinstance(text,str) or not 1 <= len(text) <= 120 or not text.isprintable(): return self._send(422,{"error":"text must be 1-120 printable characters"})
                type_text(text)
            elif action == "enter": pyautogui.press("enter")
            else: return self._send(422, {"error": "unsupported action"})
        except pyautogui.FailSafeException:
            active = False; stopped = True
            return self._send(423, {"error": "PyAutoGUI fail-safe stopped control"})
        last_at = time.monotonic(); last_action = action
        self._send(200, {"ok": True, "action": action, "x": x, "y": y,
                         "from": [start_x, start_y], "to": [x, y],
                         "bounded_window": "BHASHALEARN Desktop Control QA",
                         "bounded_region": "left disposable test-control column"})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server_thread = threading.Thread(target=server.serve_forever, name="bhashalearn-companion-http", daemon=True)
    server_thread.start()
    print(f"Desktop companion listening on http://{HOST}:{PORT}")
    if SHOW_PAIRING_TOKEN:
        print(f"Pairing token (keep private): {TOKEN}", flush=True)
    try:
        # Tk owns the Windows message loop and must be created on the main thread.
        _call_ui_mainloop()
    except KeyboardInterrupt: pass
    finally:
        background_stop.set()
        winsound.PlaySound(None, winsound.SND_PURGE)
        _end_calls_on_shutdown()
        if call_ui_root is not None:
            try: call_ui_root.after(0, call_ui_root.quit)
            except tk.TclError: pass
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)
