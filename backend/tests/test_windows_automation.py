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


@pytest.mark.parametrize("outcome", ["move", "edge", "click", "duplicate", "changed", "wrong_window", "obscured",
                                     "renamed_after_move", "resized_after_move", "disabled_after_move", "left_qa_tab"])
def test_qa_pointer_is_bounded_to_the_approved_window(monkeypatch, outcome):
    bounds = SimpleNamespace(left=100, top=100, right=600, bottom=600)
    rect = SimpleNamespace(left=200, top=200, right=300, bottom=260)
    moved = False
    button = SimpleNamespace(
        element_info=SimpleNamespace(name="Changed" if outcome == "changed" else "Search"),
        rectangle=lambda: rect, is_visible=lambda: True,
        is_enabled=lambda: not (moved and outcome == "disabled_after_move"),
    )
    window = SimpleNamespace(
        rectangle=lambda: bounds, window_text=lambda: "Another tab" if moved and outcome == "left_qa_tab" else "BHASHALEARN Desktop Control QA",
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
    position = SimpleNamespace(x=580 if outcome == "edge" else 200, y=200)
    clicks = []
    monkeypatch.setattr(windows_automation.pyautogui, "position", lambda: position)

    def move(x, y, **_):
        nonlocal moved
        position.x, position.y = x, y
        moved = True
        if outcome == "renamed_after_move":
            button.element_info.name = "Changed"
        if outcome == "resized_after_move":
            rect.right += 5

    monkeypatch.setattr(windows_automation.pyautogui, "moveTo", move)
    monkeypatch.setattr(windows_automation.pyautogui, "click", lambda x, y: clicks.append((x, y)))
    payload = {"action": "move_qa_pointer", "direction": "right"} if outcome in {"move", "edge"} else {
        "action": "click_qa_control", "target_id": "button", "target_name": "Search",
    }
    if outcome in {"move", "edge", "click"}:
        result = windows_automation.execute_action(payload, snapshot_id="snap", active_window_id="window",
                                                   type_text=lambda _: None, cancel_check=lambda: None)
        assert result["cursor"] == {"move": [280, 200], "edge": [591, 200], "click": [250, 230]}[outcome]
    else:
        with pytest.raises(RuntimeError):
            windows_automation.execute_action(payload, snapshot_id="snap", active_window_id="window",
                                               type_text=lambda _: None, cancel_check=lambda: None)
    assert clicks == ([(250, 230)] if outcome == "click" else [])


@pytest.mark.parametrize("outcome", ["success", "duplicate", "disabled", "password", "readonly", "switched", "mismatch", "stopped", "unavailable", "write_error"])
def test_qa_dictation_writes_only_the_approved_field(monkeypatch, outcome):
    writes = []
    field_value = SimpleNamespace(CurrentIsReadOnly=outcome == "readonly", CurrentValue="before")
    def set_value(value):
        writes.append(value)
        if outcome == "write_error":
            raise OSError("UI Automation provider disconnected")
        if outcome != "mismatch":
            field_value.CurrentValue = value
    field_value.SetValue = set_value
    info = SimpleNamespace(name="Permitted text field",
                           element=SimpleNamespace(CurrentIsPassword=outcome == "password"))
    field = SimpleNamespace(element_info=info, iface_value=None if outcome == "unavailable" else field_value,
                            is_visible=lambda: True, is_enabled=lambda: outcome != "disabled")
    window = SimpleNamespace(window_text=lambda: "BHASHALEARN Desktop Control QA",
                             descendants=lambda **_: [field, field] if outcome == "duplicate" else [field])
    entries = {
        "window": {"kind": "window", "app_id": "edge", "handle": 42, "wrapper": window},
        "field": {"kind": "text", "handle": 42, "wrapper": field, "label": "Permitted text field"},
    }
    monkeypatch.setattr(windows_automation, "_cached_target", lambda _, target: entries[target])
    foreground = iter([42, 9] if outcome == "switched" else [42, 42])
    monkeypatch.setattr(windows_automation, "_foreground_handle", lambda: next(foreground))
    value = "Hello, నమస్కారం!"
    payload = {"action": "type_qa_text", "target_id": "field", "target_name": "Permitted text field", "text": value}
    checks = 0
    def check_stop():
        nonlocal checks
        checks += 1
        if outcome == "stopped" and checks > 1:
            raise RuntimeError("Emergency Stop")
    def execute():
        return windows_automation.execute_action(payload, snapshot_id="snap", active_window_id="window",
                                                 type_text=lambda _: pytest.fail("Global typing must not be used"),
                                                 cancel_check=check_stop)
    if outcome == "success":
        assert execute()["typed_characters"] == len(value)
        assert field_value.CurrentValue == value
    else:
        with pytest.raises(RuntimeError):
            execute()
    assert writes == ([value] if outcome in {"success", "mismatch", "write_error"} else [])


@pytest.mark.parametrize("outcome", ["success", "already_filled", "invalid_value", "wrong_id", "readonly", "partial", "stop", "switched_during_lookup"])
def test_demo_autofill_binds_and_verifies_both_fields(monkeypatch, outcome):
    writes = []
    edits = []
    fields = []
    entries = {}
    for index, (label, text) in enumerate(windows_automation.DEMO_FORM_VALUES.items()):
        value = SimpleNamespace(CurrentValue=text if outcome == "already_filled" else "",
                                CurrentIsReadOnly=index == 1 and outcome == "readonly")

        def write(new_value, index=index, value=value):
            if index == 1 and outcome == "partial":
                raise OSError("write failed")
            writes.append(new_value)
            value.CurrentValue = new_value

        value.SetValue = write
        element = SimpleNamespace(CurrentAutomationId="wrong" if index == 1 and outcome == "wrong_id"
                                  else windows_automation.DEMO_FORM_IDS[label], CurrentIsPassword=False)
        edit = SimpleNamespace(element_info=SimpleNamespace(name=label, element=element),
                               is_visible=lambda: True, is_enabled=lambda: True, iface_value=value)
        edits.append(edit)
        entries[str(index)] = {"kind": "text", "handle": 42, "label": label, "wrapper": edit}
        fields.append({"label": label, "target_id": str(index), "value": text})
    if outcome == "invalid_value":
        fields[1]["value"] = "another@example.test"

    window = SimpleNamespace(window_text=lambda: "BHASHALEARN Desktop Control QA", descendants=lambda **_: edits)
    entries["window"] = {"kind": "window", "handle": 42, "app_id": "edge", "wrapper": window}
    monkeypatch.setattr(windows_automation, "_cached_target", lambda _, target: entries[target])
    foreground = iter([42, 7]) if outcome == "switched_during_lookup" else None
    monkeypatch.setattr(windows_automation, "_foreground_handle", lambda: next(foreground) if foreground else 42)

    def cancel_check():
        if outcome == "stop" and writes:
            raise RuntimeError("Emergency Stop")

    def execute():
        return windows_automation.execute_action({"action": "fill_qa_demo_form", "fields": fields},
                                                 snapshot_id="snap", active_window_id="window",
                                                 type_text=lambda _: pytest.fail("Global typing must not be used"),
                                                 cancel_check=cancel_check)
    if outcome in {"success", "already_filled"}:
        assert execute()["verified_fields"] == 2
        assert [edit.iface_value.CurrentValue for edit in edits] == [field["value"] for field in fields]
    else:
        with pytest.raises(RuntimeError):
            execute()
    assert writes == ([field["value"] for field in fields] if outcome == "success" else
                      [fields[0]["value"]] if outcome in {"partial", "stop"} else [])
