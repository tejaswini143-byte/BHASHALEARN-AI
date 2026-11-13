"""Loopback HTTP tests for the Windows companion; all mouse APIs are mocked."""
import json
from datetime import datetime, timezone
from threading import Event, Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

import pytest

from scripts import desktop_companion as companion


@pytest.fixture
def companion_server(monkeypatch):
    monkeypatch.setattr(companion, "TOKEN", "qa-test-token")
    monkeypatch.setattr(companion, "active", False)
    monkeypatch.setattr(companion, "stopped", False)
    monkeypatch.setattr(companion, "last_action", "")
    monkeypatch.setattr(companion, "last_at", 0.0)
    monkeypatch.setattr(companion, "desktop_stop", Event())
    monkeypatch.setattr(companion, "pending_execution_confirmations", {})
    monkeypatch.setattr(companion, "active_qa_bounds", lambda: (120, 80, 640, 480))
    server = ThreadingHTTPServer(("127.0.0.1", 0), companion.Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def request(base, path, payload=None, token="qa-test-token", origin=None):
    headers = {"Authorization": f"Bearer {token}"}
    if origin:
        headers["Origin"] = origin
    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode()
    req = Request(base + path, data=body, headers=headers, method="GET" if path in {"/health", "/pair", "/desktop/snapshot"} else "POST")
    try:
        with urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read())
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_companion_requires_bearer_token(companion_server):
    status, result = request(companion_server, "/health", token="wrong")
    assert status == 401
    assert result["error"] == "unauthorized"


def test_pairing_token_is_released_only_to_allowlisted_local_app(companion_server):
    status, result = request(companion_server, "/pair", origin="http://127.0.0.1:5201")
    assert status == 200
    assert result["token"] == "qa-test-token"
    status, result = request(companion_server, "/pair", origin="https://untrusted.example")
    assert status == 403
    assert "only to the local BHASHALEARN app" in result["error"]


def test_background_connection_accepts_documented_loopback_backend_port(companion_server, monkeypatch):
    monkeypatch.setattr(companion, "background_config", {})
    monkeypatch.setattr(companion.httpx, "get", lambda *_args, **_kwargs: type("Response", (), {"status_code": 200})())
    origin = "http://127.0.0.1:15199"
    payload = {"api_base": "http://127.0.0.1:18027/api/v1", "access_token": "synthetic-session-token"}
    status, result = request(companion_server, "/background/enable", payload, origin=origin)
    assert status == 200
    assert result["enabled"] is True
    assert companion.background_config["api_base"] == payload["api_base"]
    status, result = request(companion_server, "/background/enable", {
        **payload, "api_base": "http://127.0.0.1:18028/api/v1"
    }, origin=origin)
    assert status == 422
    assert "Only an authenticated loopback" in result["error"]


def test_repeated_reminder_poll_reserves_only_one_call_window(monkeypatch):
    class Root:
        def __init__(self):
            self.callbacks = []
        def after(self, delay, callback):
            self.callbacks.append(callback)
    root = Root()
    monkeypatch.setattr(companion, "call_ui_root", root)
    monkeypatch.setattr(companion, "call_windows", {})
    call = {"id": "one-pending-call", "title": "Disposable reminder"}
    companion._show_incoming_call(call)
    companion._show_incoming_call(call)
    assert len(root.callbacks) == 1
    assert companion.call_windows[call["id"]]["creating"] is True


def test_companion_shutdown_ends_displayed_calls_and_clears_local_state(monkeypatch):
    calls = []
    entry = {"call": {"id": "qa-call-1"}, "speaking": True, "listening": True}
    monkeypatch.setattr(companion, "call_windows", {"qa-call-1": entry})
    monkeypatch.setattr(companion, "_background_request",
        lambda method, path, **kwargs: calls.append((method, path)))
    monkeypatch.setattr(companion.winsound, "PlaySound", lambda *args: None)

    companion._end_calls_on_shutdown()

    assert calls == [("POST", "/assistant/local-calls/qa-call-1/end")]
    assert entry["speaking"] is False and entry["listening"] is False
    assert companion.call_windows == {}


def test_answered_call_arms_configured_duration_limit(monkeypatch):
    class Widget:
        def configure(self, **kwargs): pass
        def winfo_exists(self): return True
    class Root:
        def __init__(self): self.scheduled = []
        def after(self, delay, callback):
            handle = f"after-{len(self.scheduled)}"
            self.scheduled.append((delay, callback, handle))
            return handle
    root = Root()
    monkeypatch.setattr(companion, "_background_request", lambda *args, **kwargs: {
        "greeting": "Hello", "language": "en", "max_duration_minutes": 20,
    })
    monkeypatch.setattr(companion, "_play_speech", lambda *args, **kwargs: None)
    monkeypatch.setattr(companion, "_set_call_status", lambda *args, **kwargs: None)
    data = {"root": root, "window": Widget(), "status": Widget(), "title": Widget(),
            "answer": Widget(), "speak": Widget(), "interrupt": Widget(), "reply": Widget()}
    call = {"id": "duration-call", "title": "Disposable call", "language": "en"}
    companion._answer_call(call, data)
    assert data["duration_timer"] == root.scheduled[1][2]
    assert root.scheduled[1][0] == 20 * 60_000


def test_call_extension_rearms_native_duration_timer(monkeypatch):
    class Widget:
        def configure(self, **kwargs): pass
        def winfo_exists(self): return True
    class Root:
        def __init__(self): self.scheduled = []; self.cancelled = []
        def after(self, delay, callback):
            handle = f"after-{len(self.scheduled)}"
            self.scheduled.append((delay, callback, handle))
            return handle
        def after_cancel(self, handle): self.cancelled.append(handle)
    root = Root()
    answered_at = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(companion, "_background_request", lambda *args, **kwargs: {
        "max_duration_minutes": 40, "answered_at": answered_at,
    })
    call = {"id": "extendable-call", "max_duration_minutes": 30}
    data = {"root": root, "status": Widget(), "duration_timer": "old-timer"}
    companion._extend_call(call, data, 10)
    assert call["max_duration_minutes"] == 40
    assert root.scheduled[0][0] == 0
    root.scheduled[0][1]()
    assert root.cancelled == ["old-timer"]
    assert abs(root.scheduled[1][0] - 40 * 60_000) < 1000


def test_browser_preflight_allows_only_local_app_origin(companion_server):
    req = Request(companion_server + "/action", headers={
        "Origin": "http://127.0.0.1:5201",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }, method="OPTIONS")
    with urlopen(req, timeout=3) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5201"
        assert response.read() == b""
    qa2 = Request(companion_server + "/action", headers={
        "Origin": "http://127.0.0.1:5202",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }, method="OPTIONS")
    with urlopen(qa2, timeout=3) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5202"
    qa3 = Request(companion_server + "/action", headers={
        "Origin": "http://127.0.0.1:5203",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }, method="OPTIONS")
    with urlopen(qa3, timeout=3) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5203"


def test_actions_require_explicit_activation(companion_server):
    status, result = request(companion_server, "/action", {"action": "center"})
    assert status == 423
    assert "disabled" in result["error"]


def test_uia_snapshot_is_available_only_to_authenticated_local_app(companion_server, monkeypatch):
    monkeypatch.setattr(companion.windows_automation, "get_snapshot", lambda: {
        "snapshot_id": "snapshot", "active_window_id": "w-10", "focused_target_id": None,
        "active_app": "Notepad", "targets": [],
    })
    status, result = request(companion_server, "/desktop/snapshot", token="wrong",
                             origin="http://127.0.0.1:5173")
    assert status == 401
    status, result = request(companion_server, "/desktop/snapshot", origin="https://untrusted.example")
    assert status == 403
    status, result = request(companion_server, "/desktop/snapshot", origin="http://127.0.0.1:5173")
    assert status == 200 and result["active_app"] == "Notepad"


def test_desktop_execution_requires_enabled_control_and_local_origin(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion.windows_automation, "execute_action", lambda action, **kwargs: calls.append(action) or {"ok": True, "action": action["action"]})
    payload = {"snapshot_id": "snap", "action": {"action": "open_app", "app_id": "notepad"}}
    status, _ = request(companion_server, "/desktop/execute", payload, origin="http://127.0.0.1:5173")
    assert status == 423 and not calls

    companion.active = True
    companion.stopped = False
    companion.desktop_stop.clear()
    status, result = request(companion_server, "/desktop/execute", payload, origin="https://untrusted.example")
    assert status == 403 and not calls
    status, result = request(companion_server, "/desktop/execute", payload, origin="http://127.0.0.1:5173")
    assert status == 409 and not calls
    status, approval = request(companion_server, "/desktop/confirm", payload, origin="http://127.0.0.1:5173")
    assert status == 200 and approval["confirmation_token"]
    status, result = request(companion_server, "/desktop/execute", {
        **payload, "confirmation_token": approval["confirmation_token"]
    }, origin="http://127.0.0.1:5173")
    assert status == 200 and result["action"] == "open_app"
    assert calls == [payload["action"]]
    status, _ = request(companion_server, "/desktop/execute", {
        **payload, "confirmation_token": approval["confirmation_token"]
    }, origin="http://127.0.0.1:5173")
    assert status == 409 and calls == [payload["action"]]


def test_confirmation_is_one_use_and_bound_to_the_exact_action(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion.windows_automation, "execute_action", lambda action, **kwargs: calls.append(action) or {"ok": True, "action": action["action"]})
    companion.active = True
    companion.stopped = False
    companion.desktop_stop.clear()
    origin = "http://127.0.0.1:15199"
    payload = {"snapshot_id": "snap", "action": {"action": "open_app", "app_id": "notepad"}}
    status, approval = request(companion_server, "/desktop/confirm", payload, origin=origin)
    assert status == 200 and calls == []
    token = approval["confirmation_token"]
    changed = {"snapshot_id": "snap", "action": {"action": "open_app", "app_id": "calculator"}, "confirmation_token": token}
    status, _ = request(companion_server, "/desktop/execute", changed, origin=origin)
    assert status == 409 and calls == []
    status, _ = request(companion_server, "/desktop/execute", {**payload, "confirmation_token": token}, origin=origin)
    assert status == 409 and calls == []

    status, approval = request(companion_server, "/desktop/confirm", payload, origin=origin)
    status, result = request(companion_server, "/desktop/execute", {**payload, "confirmation_token": approval["confirmation_token"]}, origin=origin)
    assert status == 200 and result["action"] == "open_app" and calls == [payload["action"]]


def test_emergency_stop_cancels_following_desktop_requests(companion_server, monkeypatch):
    companion.active = True
    companion.stopped = False
    companion.desktop_stop.clear()
    status, result = request(companion_server, "/stop")
    assert status == 200 and result["active"] is False
    assert companion.desktop_stop.is_set()
    status, result = request(companion_server, "/desktop/execute",
                             {"snapshot_id": "snap", "action": {"action": "open_app", "app_id": "notepad"}},
                             origin="http://127.0.0.1:5173")
    assert status == 423 and "disabled" in result["error"]


def test_authenticated_health_confirms_stop_and_fresh_enablement_is_required(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion.windows_automation, "execute_action", lambda action, **kwargs: calls.append(action) or {"ok": True, "action": action["action"]})
    companion.active = True
    companion.stopped = False
    companion.desktop_stop.clear()
    status, before = request(companion_server, "/health")
    assert status == 200 and before["active"] is True and before["stopped"] is False

    origin = "http://127.0.0.1:15199"
    payload = {"snapshot_id": "snap", "action": {"action": "open_app", "app_id": "notepad"}}
    status, approval = request(companion_server, "/desktop/confirm", payload, origin=origin)
    assert status == 200

    status, stopped = request(companion_server, "/stop")
    assert status == 200 and stopped["active"] is False
    status, health = request(companion_server, "/health")
    assert status == 200 and health["active"] is False and health["stopped"] is True

    status, _ = request(companion_server, "/desktop/execute", {
        **payload, "confirmation_token": approval["confirmation_token"]
    }, origin=origin)
    assert status == 423 and calls == []

    status, enabled = request(companion_server, "/activate")
    assert status == 200 and enabled["active"] is True
    status, health = request(companion_server, "/health")
    assert status == 200 and health["active"] is True and health["stopped"] is False
    status, _ = request(companion_server, "/desktop/execute", payload, origin=origin)
    assert status == 409 and calls == []
    status, approval = request(companion_server, "/desktop/confirm", payload, origin=origin)
    status, result = request(companion_server, "/desktop/execute", {
        **payload, "confirmation_token": approval["confirmation_token"]
    }, origin=origin)
    assert status == 200 and result["action"] == "open_app" and calls == [payload["action"]]


def test_active_action_stays_inside_qa_window(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (300, 250))
    monkeypatch.setattr(companion.pyautogui, "size", lambda: (1920, 1080))
    monkeypatch.setattr(companion.pyautogui, "moveTo", lambda *args: calls.append(args))
    status, result = request(companion_server, "/action", {"action": "center"})
    assert status == 200
    assert 120 <= result["x"] < 376 and 80 <= result["y"] < 560
    assert result["bounded_window"] == companion.QA_WINDOW_TITLE
    assert result["bounded_region"] == "left disposable test-control column"
    assert result["from"] == [300, 250]
    assert result["to"] == [result["x"], result["y"]]
    assert calls and 120 <= calls[0][0] < 376 and 80 <= calls[0][1] < 560


def test_click_is_blocked_when_pointer_is_outside_qa_window(companion_server, monkeypatch):
    clicked = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (50, 50))
    monkeypatch.setattr(companion.pyautogui, "click", lambda: clicked.append(True))
    status, result = request(companion_server, "/action", {"action": "click"})
    assert status == 423
    assert not clicked


def test_click_is_limited_to_disposable_test_column(companion_server, monkeypatch):
    clicked = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (500, 250))
    monkeypatch.setattr(companion.pyautogui, "click", lambda: clicked.append(True))
    status, result = request(companion_server, "/action", {"action": "click"})
    assert status == 423
    assert "test-control column" in result["error"]
    assert not clicked


@pytest.mark.parametrize(("action", "method", "payload"), [
    ("right", "moveTo", {}), ("left", "moveTo", {}), ("up", "moveTo", {}),
    ("down", "moveTo", {}), ("click", "click", {}),
    ("move_to", "moveTo", {"x": 200, "y": 200}),
    ("double_click", "doubleClick", {}), ("scroll_down", "scroll", {}),
    ("scroll_up", "scroll", {}), ("type", "type_text", {"text": "QA sample"}),
    ("enter", "press", {}),
])
def test_companion_dispatches_allowlisted_actions_to_mocked_desktop(companion_server, monkeypatch, action, method, payload):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (250, 250))
    monkeypatch.setattr(companion.pyautogui, "size", lambda: (1920, 1080))
    target = companion if method == "type_text" else companion.pyautogui
    monkeypatch.setattr(target, method, lambda *args: calls.append((method, args)))
    status, result = request(companion_server, "/action", {"action": action, **payload})
    assert status == 200
    assert result["action"] == action
    assert calls and calls[0][0] == method


def test_emergency_stop_disables_future_actions(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (250, 250))
    monkeypatch.setattr(companion.pyautogui, "click", lambda: calls.append("click"))
    stop_status, stop_result = request(companion_server, "/stop")
    action_status, action_result = request(companion_server, "/action", {"action": "click"})
    assert stop_status == 200 and stop_result["active"] is False
    assert action_status == 423 and "disabled" in action_result["error"]
    assert not calls


def test_semantic_target_cursor_move_is_bounded(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (250, 250))
    monkeypatch.setattr(companion.pyautogui, "moveTo", lambda *args: calls.append(args))
    status, result = request(companion_server, "/action", {"action": "move_to", "x": 180, "y": 220})
    assert status == 200
    assert result["to"] == [180, 220]
    assert calls == [(180, 220, 0.2)]


def test_semantic_target_move_can_enter_safe_region_from_elsewhere_in_same_window(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (500, 250))
    monkeypatch.setattr(companion.pyautogui, "moveTo", lambda *args: calls.append(args))
    status, result = request(companion_server, "/action", {"action": "move_to", "x": 180, "y": 220})
    assert status == 200
    assert result["from"] == [500, 250]
    assert result["to"] == [180, 220]
    assert calls == [(180, 220, 0.2)]


def test_semantic_target_cursor_move_rejects_outside_test_column(companion_server, monkeypatch):
    calls = []
    monkeypatch.setattr(companion, "active", True)
    monkeypatch.setattr(companion.pyautogui, "position", lambda: (250, 250))
    monkeypatch.setattr(companion.pyautogui, "moveTo", lambda *args: calls.append(args))
    status, result = request(companion_server, "/action", {"action": "move_to", "x": 600, "y": 220})
    assert status == 423
    assert "outside the bounded" in result["error"]
    assert not calls


def test_foreground_window_must_match_disposable_page(monkeypatch):
    class Window:
        title = "ChatGPT - Google Chrome"
        left, top, width, height = 0, 0, 1920, 1080

    monkeypatch.setattr(companion.pygetwindow, "getActiveWindow", lambda: Window())
    with pytest.raises(RuntimeError, match="QA page to the foreground"):
        companion.active_qa_bounds()
