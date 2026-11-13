from types import SimpleNamespace

import pytest

from scripts import windows_automation


def test_target_action_keeps_the_validated_snapshot_id(monkeypatch):
    calls = []
    target = {
        "kind": "text",
        "wrapper": SimpleNamespace(set_focus=lambda: None),
        "handle": 42,
        "label": "QA test target",
        "rect": [10, 20, 30, 40],
    }
    monkeypatch.setattr(
        windows_automation,
        "_cached_target",
        lambda snapshot_id, target_id: calls.append((snapshot_id, target_id)) or target,
    )
    monkeypatch.setattr(windows_automation, "_foreground_handle", lambda: 42)
    monkeypatch.setattr(windows_automation.pyautogui, "moveTo", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        windows_automation.pyautogui,
        "position",
        lambda: SimpleNamespace(x=20, y=30),
    )

    result = windows_automation.execute_action(
        {"action": "move_to_target", "target_id": "control-1"},
        snapshot_id="fresh-snapshot",
        type_text=lambda _text: None,
        cancel_check=lambda: None,
    )

    assert calls == [("fresh-snapshot", "control-1")]
    assert result["ok"] is True
    assert result["cursor"] == [20, 30]


def test_switch_window_waits_for_foreground_activation(monkeypatch):
    foreground = iter([0, 42, 42])
    target = {
        "kind": "window",
        "wrapper": SimpleNamespace(set_focus=lambda: None),
        "handle": 42,
        "label": "QA window",
    }
    monkeypatch.setattr(windows_automation, "_cached_target", lambda *_args: target)
    monkeypatch.setattr(windows_automation, "_foreground_handle", lambda: next(foreground))
    result = windows_automation.execute_action(
        {"action": "switch_window", "target_id": "window-1"},
        snapshot_id="fresh-snapshot",
        type_text=lambda _text: None,
        cancel_check=lambda: None,
    )
    assert result == {"ok": True, "action": "switch_window", "target": "QA window"}


@pytest.mark.parametrize("outcome", ["existing", "new", "stopped"])
def test_notepad_verifies_only_a_new_window_and_respects_stop(monkeypatch, tmp_path, outcome):
    focused = []
    launched = []
    executable = tmp_path / "notepad.exe"
    executable.touch()
    existing = {"handle": 42, "id": "w-2a", "app_id": "notepad",
                "wrapper": SimpleNamespace(set_focus=lambda: focused.append(42))}
    new = {"handle": 43, "id": "w-2b", "app_id": "notepad",
           "wrapper": SimpleNamespace(set_focus=lambda: focused.append(43))}
    monkeypatch.setattr(windows_automation.shutil, "which", lambda _: str(executable))
    monkeypatch.setattr(windows_automation.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(windows_automation.subprocess, "Popen", lambda args, **_: launched.append(args))
    monkeypatch.setattr(windows_automation, "_windows",
                        lambda: [existing, new] if launched and outcome != "existing" else [existing])
    ticks = iter([0, 0, 11])
    monkeypatch.setattr(windows_automation.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(windows_automation.time, "sleep", lambda _: None)

    def cancel_check():
        if launched and outcome == "stopped":
            raise RuntimeError("Emergency Stop")

    def execute():
        return windows_automation.execute_action({"action": "open_app", "app_id": "notepad"},
                                                 type_text=lambda _: None, cancel_check=cancel_check)

    if outcome == "new":
        assert execute()["verified_window"] == "w-2b"
        assert focused == [43]
    else:
        error = "Emergency Stop" if outcome == "stopped" else "No new Notepad window was verified"
        with pytest.raises(RuntimeError, match=error):
            execute()
        assert focused == []
    assert len(launched) == 1


@pytest.mark.parametrize("url", sorted(windows_automation.APPROVED_LINKS))
def test_approved_link_dispatches_exact_url(monkeypatch, url):
    opened = []
    monkeypatch.setattr(windows_automation.webbrowser, "open", lambda value, **_: opened.append(value) or True)
    result = windows_automation.execute_action({"action": "open_named_link", "url": url},
                                               type_text=lambda _: None, cancel_check=lambda: None)
    assert opened == [url]
    assert result == {"ok": True, "action": "open_named_link", "url": url}


@pytest.mark.parametrize("url", ["https://www.youtube.com.example.org/", "https://www.youtube.com/results", ["https://www.youtube.com/"]])
def test_unapproved_link_never_dispatches(monkeypatch, url):
    def unexpected_open(*args, **kwargs):
        pytest.fail("An unapproved destination reached the browser")

    monkeypatch.setattr(windows_automation.webbrowser, "open", unexpected_open)
    with pytest.raises(RuntimeError, match="Choose an approved link"):
        windows_automation.execute_action({"action": "open_named_link", "url": url},
                                          type_text=lambda _: None, cancel_check=lambda: None)


@pytest.mark.parametrize("browser_error", [False, True])
def test_approved_link_reports_browser_dispatch_failure(monkeypatch, browser_error):
    def open_link(*args, **kwargs):
        if browser_error:
            raise OSError("Shell handler failed")
        return False

    monkeypatch.setattr(windows_automation.webbrowser, "open", open_link)
    with pytest.raises(RuntimeError, match="Check that a default browser is configured"):
        windows_automation.execute_action({"action": "open_named_link", "url": "https://chatgpt.com/"},
                                          type_text=lambda _: None, cancel_check=lambda: None)


@pytest.mark.parametrize("outcome", ["move", "click", "duplicate", "changed", "wrong_window", "obscured"])
def test_qa_pointer_is_bounded_to_the_approved_window(monkeypatch, outcome):
    bounds = SimpleNamespace(left=100, top=100, right=600, bottom=600)
    rect = SimpleNamespace(left=200, top=200, right=300, bottom=260)
    button = SimpleNamespace(
        element_info=SimpleNamespace(name="Changed" if outcome == "changed" else "Search"),
        rectangle=lambda: rect, is_visible=lambda: True, is_enabled=lambda: True,
    )
    window = SimpleNamespace(
        rectangle=lambda: bounds, window_text=lambda: "BHASHALEARN Desktop Control QA",
        descendants=lambda **_: [button, button] if outcome == "duplicate" else [button],
    )
    entries = {
        "window": {"kind": "window", "app_id": "edge", "handle": 42, "wrapper": window},
        "button": {"kind": "button", "handle": 42, "wrapper": button, "label": "Search",
                   "rect": [200, 200, 300, 260]},
    }
    monkeypatch.setattr(windows_automation, "_cached_target", lambda _, target_id: entries[target_id])
    monkeypatch.setattr(windows_automation, "_foreground_handle", lambda: 7 if outcome == "wrong_window" else 42)
    monkeypatch.setattr(windows_automation, "Desktop", lambda **_: SimpleNamespace(
        from_point=lambda *_: SimpleNamespace(element_info=None) if outcome == "obscured" else button,
    ))
    position = SimpleNamespace(x=200, y=200)
    clicks = []
    monkeypatch.setattr(windows_automation.pyautogui, "position", lambda: position)

    def move(x, y, **_):
        position.x, position.y = x, y

    monkeypatch.setattr(windows_automation.pyautogui, "moveTo", move)
    monkeypatch.setattr(windows_automation.pyautogui, "click", lambda x, y: clicks.append((x, y)))
    payload = {"action": "move_qa_pointer", "direction": "right"} if outcome == "move" else {
        "action": "click_qa_control", "target_id": "button", "target_name": "Search",
    }
    if outcome in {"move", "click"}:
        result = windows_automation.execute_action(payload, snapshot_id="snap", active_window_id="window",
                                                   type_text=lambda _: None, cancel_check=lambda: None)
        assert result["cursor"] == ([280, 200] if outcome == "move" else [250, 230])
    else:
        with pytest.raises(RuntimeError):
            windows_automation.execute_action(payload, snapshot_id="snap", active_window_id="window",
                                               type_text=lambda _: None, cancel_check=lambda: None)
    assert clicks == ([(250, 230)] if outcome == "click" else [])
