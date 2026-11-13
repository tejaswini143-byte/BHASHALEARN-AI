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
