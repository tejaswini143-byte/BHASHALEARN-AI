from types import SimpleNamespace

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
