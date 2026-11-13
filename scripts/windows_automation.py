"""Bounded Windows UI Automation helpers for the local BHASHALEARN companion."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import shutil
import subprocess
import threading
import time
import secrets
import tempfile
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlsplit

import pyautogui
# pywinauto's COM wrapper generator otherwise falls back to the profile's
# AppData folder when site-packages is read-only. Keep generated UIA wrappers
# in the OS temp cache; never write them into the repository or user profile.
_comtypes_cache = Path(tempfile.gettempdir()) / "bhashalearn-comtypes-cache"
_comtypes_cache.mkdir(parents=True, exist_ok=True)
try:
    import comtypes.gen
    comtypes.gen.__path__ = [str(_comtypes_cache)]
except ImportError:
    pass
from pywinauto import Desktop


SUPPORTED_APPS = {"notepad": "Notepad", "chrome": "Google Chrome", "edge": "Microsoft Edge"}
APPROVED_LINKS = frozenset({"https://www.youtube.com/", "https://chatgpt.com/", "https://www.google.com/"})
PROCESS_APPS = {"notepad.exe": "notepad", "chrome.exe": "chrome", "msedge.exe": "edge"}
SENSITIVE_LABEL = re.compile(r"password|passcode|one[- ]time code|\botp\b|credit card|cvv|bank account|social security|passport|\bssn\b", re.I)
MAX_CONTROLS = 30
SNAPSHOT_TTL = 90
_cache_lock = threading.Lock()
_snapshots: dict[str, dict] = {}


def _process_image(pid: int) -> str | None:
    if os.name != "nt" or not pid:
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                     wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        length = ctypes.c_ulong(1024)
        buffer = ctypes.create_unicode_buffer(length.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def _windows() -> list[dict]:
    from pywinauto import handleprops
    entries = []
    for wrapper in Desktop(backend="uia").windows():
        try:
            handle = int(wrapper.handle)
            if not handle or not handleprops.isvisible(handle):
                continue
            info = wrapper.element_info
            pid = int(info.process_id or 0)
            path = _process_image(pid)
            process_name = Path(path).name.casefold() if path else ""
            app_id = PROCESS_APPS.get(process_name)
            # Keep all visible top-level windows addressable by local process name,
            # while exposing no document title or window text to Gemini.
            if not app_id:
                app_id = re.sub(r"[^a-z0-9_-]", "", process_name.removesuffix(".exe"))[:32]
            if not app_id:
                continue
            entries.append({"id": f"w-{handle:x}", "handle": handle,
                            "app_id": app_id, "label": SUPPORTED_APPS.get(app_id, app_id),
                            "wrapper": wrapper, "pid": pid})
        except Exception:
            continue
    return entries


def _control_kind(control_type: str, app_id: str = "") -> str | None:
    if app_id == "notepad" and control_type in {"Document", "Edit"}:
        return "text"
    return {"Button": "button", "Hyperlink": "link", "Edit": "text",
            "ComboBox": "search", "MenuItem": "button"}.get(control_type)


def _is_pointer_qa_window(app_id, wrapper) -> bool:
    if app_id not in {"chrome", "edge"}:
        return False
    try:
        return wrapper.window_text().startswith("BHASHALEARN Desktop Control QA")
    except Exception:
        return False


def get_snapshot() -> dict:
    """Return visible window names and a bounded active-window UIA target catalog.

    Window/document titles and editable values are deliberately not returned.
    """
    entries = _windows()
    all_window_count = len(entries)
    foreground = int(ctypes.windll.user32.GetForegroundWindow()) if os.name == "nt" else 0
    active_entry = next((item for item in entries if item["handle"] == foreground), None)
    if active_entry and active_entry not in entries[:10]:
        entries = [active_entry, *[item for item in entries if item is not active_entry][:9]]
    else:
        entries = entries[:10]
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["app_id"]] = counts.get(entry["app_id"], 0) + 1
    seen: dict[str, int] = {}
    targets: list[dict] = []
    element_cache: dict[str, dict] = {}
    focused_target_id = None
    for entry in entries:
        seen[entry["app_id"]] = seen.get(entry["app_id"], 0) + 1
        ordinal = f" window {seen[entry['app_id']]}" if counts[entry["app_id"]] > 1 else ""
        label = entry["label"] + ordinal
        targets.append({"id": entry["id"], "role": "window", "name": label, "kind": "window",
                        "active": entry["handle"] == foreground})
        element_cache[entry["id"]] = {"kind": "window", "wrapper": entry["wrapper"],
                                      "handle": entry["handle"], "app_id": entry["app_id"], "label": label}

    if active_entry:
        counter = 0
        try:
            descendants = active_entry["wrapper"].descendants()
        except Exception:
            descendants = []
        for wrapper in descendants:
            if counter >= MAX_CONTROLS:
                break
            try:
                info = wrapper.element_info
                if hasattr(wrapper, "is_visible") and not wrapper.is_visible():
                    continue
                if hasattr(wrapper, "is_password") and wrapper.is_password():
                    continue
                control_type = str(info.control_type or "")
                kind = _control_kind(control_type, active_entry["app_id"])
                if not kind:
                    continue
                # UIA Name is the accessible label, never the Value pattern.
                name = "Notepad document" if active_entry["app_id"] == "notepad" and kind == "text" else str(info.name or "").strip()
                if not name and kind in {"text", "search"}:
                    name = "Text field"
                if not name or len(name) > 120 or SENSITIVE_LABEL.search(name):
                    continue
                rect = wrapper.rectangle()
                if rect.width() <= 0 or rect.height() <= 0:
                    continue
                counter += 1
                target_id = f"c-{active_entry['handle']:x}-{counter}"
                targets.append({"id": target_id, "role": control_type.casefold(), "name": name, "kind": kind})
                element_cache[target_id] = {"kind": kind, "wrapper": wrapper,
                    "handle": active_entry["handle"], "app_id": active_entry["app_id"],
                    "label": name, "rect": [int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)]}
                try:
                    if wrapper.has_keyboard_focus():
                        focused_target_id = target_id
                except Exception:
                    pass
            except Exception:
                continue

    snapshot_id = secrets.token_urlsafe(18)
    cached = {"created_at": time.monotonic(), "elements": element_cache,
              "active_window_id": active_entry["id"] if active_entry else None}
    with _cache_lock:
        now = time.monotonic()
        for key in list(_snapshots):
            if now - _snapshots[key]["created_at"] > SNAPSHOT_TTL:
                _snapshots.pop(key, None)
        _snapshots[snapshot_id] = cached
        while len(_snapshots) > 8:
            _snapshots.pop(next(iter(_snapshots)))
    return {"snapshot_id": snapshot_id,
            "active_window_id": cached["active_window_id"],
            "focused_target_id": focused_target_id,
            "targets": targets,
            "active_app": active_entry["label"] if active_entry else None,
            "pointer_qa_window": bool(active_entry and _is_pointer_qa_window(active_entry["app_id"], active_entry["wrapper"])),
            "window_count": all_window_count}


def _cached_target(snapshot_id: str, target_id: str) -> dict:
    with _cache_lock:
        snapshot = _snapshots.get(snapshot_id)
    if not snapshot or time.monotonic() - snapshot["created_at"] > SNAPSHOT_TTL:
        raise RuntimeError("The desktop view expired. Refresh the target list and try again.")
    target = snapshot["elements"].get(target_id)
    if not target:
        raise RuntimeError("The target was not in the latest Windows UI Automation snapshot.")
    if not ctypes.windll.user32.IsWindow(target["handle"]):
        raise RuntimeError("The target window has closed. Refresh the target list.")
    return target


def _foreground_handle() -> int:
    return int(ctypes.windll.user32.GetForegroundWindow())


def _launch_app(app_id: str, *, cancel_check) -> dict:
    if app_id not in SUPPORTED_APPS:
        raise RuntimeError("Only Notepad, Chrome, and Edge can be launched by voice.")
    paths = {
        "notepad": shutil.which("notepad.exe") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "notepad.exe"),
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    }
    executable = paths[app_id]
    if not Path(executable).is_file():
        located = shutil.which(Path(executable).name)
        if not located:
            raise RuntimeError(f"{SUPPORTED_APPS[app_id]} is not installed at its approved location.")
        executable = located
    before = {item["handle"] for item in _windows()}
    command = [executable]
    if app_id == "notepad":
        # Windows Notepad may restore its last private tabs when opened without
        # a document. Always direct it to a fresh empty scratch document.
        scratch = Path(tempfile.gettempdir()) / f"BHASHALEARN-Desktop-Control-{secrets.token_hex(6)}.txt"
        scratch.write_text("", encoding="utf-8")
        command.append(str(scratch))
    cancel_check()
    subprocess.Popen(command, close_fds=True)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        time.sleep(0.25)
        cancel_check()
        opened = [item for item in _windows() if item["app_id"] == app_id]
        newest = next((item for item in opened if item["handle"] not in before), None)
        if newest is None and opened and app_id != "notepad":
            newest = opened[-1]
        if newest is not None:
            cancel_check()
            newest["wrapper"].set_focus()
            return {"ok": True, "action": "open_app", "app_id": app_id,
                    "verified_window": newest["id"]}
    if app_id == "notepad":
        raise RuntimeError("No new Notepad window was verified. Check whether Notepad opened the scratch file in an existing tab before retrying.")
    raise RuntimeError(f"{SUPPORTED_APPS[app_id]} did not open a visible window within 10 seconds.")


def execute_action(payload: dict, *, type_text, cancel_check, confirmed_close: bool = False,
                   sequence_context: dict | None = None, snapshot_id: str | None = None,
                   active_window_id: str | None = None, focus_target_id: str | None = None) -> dict:
    """Execute one validated action or sequence with per-step stop checks."""
    context = sequence_context if sequence_context is not None else {}
    snapshot_id = payload.get("snapshot_id", context.get("snapshot_id", snapshot_id))
    active_window_id = payload.get("active_window_id", context.get("active_window_id", active_window_id))
    focus_target_id = payload.get("focus_target_id", context.get("focus_target_id", focus_target_id))
    cancel_check()
    action = payload.get("action")
    if action == "sequence":
        steps = payload.get("steps")
        if not isinstance(steps, list) or not 1 <= len(steps) <= 5:
            raise RuntimeError("Only one to five sequential actions are supported.")
        results = []
        for step in steps:
            cancel_check()
            results.append(execute_action(step, type_text=type_text, cancel_check=cancel_check,
                                          confirmed_close=confirmed_close, sequence_context=context,
                                          snapshot_id=snapshot_id, active_window_id=active_window_id,
                                          focus_target_id=focus_target_id))
        return {"ok": True, "action": "sequence", "steps": results}
    if action == "open_app":
        result = _launch_app(payload.get("app_id"), cancel_check=cancel_check)
        context["launched_app"] = payload.get("app_id")
        return result
    if action == "open_named_link":
        url = payload.get("url")
        if not isinstance(url, str) or url not in APPROVED_LINKS:
            raise RuntimeError("Choose an approved link: YouTube, ChatGPT, or Google.")
        cancel_check()
        failure = "Windows could not send the approved link to the default browser. Check that a default browser is configured."
        try:
            dispatched = webbrowser.open(url, new=2, autoraise=True)
        except (OSError, webbrowser.Error):
            raise RuntimeError(failure) from None
        if not dispatched:
            raise RuntimeError(failure)
        return {"ok": True, "action": action, "url": url}
    if action == "open_website":
        url = payload.get("url")
        parsed = urlsplit(url or "")
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise RuntimeError("Only a valid HTTPS website can be opened.")
        if not webbrowser.open(url, new=2, autoraise=True):
            raise RuntimeError("Windows could not open the website in the default browser.")
        return {"ok": True, "action": action, "host": parsed.hostname}
    if action == "search_web":
        query = payload.get("text")
        if not isinstance(query, str) or not query.strip() or len(query) > 120:
            raise RuntimeError("Search text must be 1-120 characters.")
        url = "https://www.google.com/search?q=" + quote_plus(query.strip())
        if not webbrowser.open(url, new=2, autoraise=True):
            raise RuntimeError("Windows could not open the search in the default browser.")
        return {"ok": True, "action": action, "destination": "Google search"}
    if action == "search_youtube":
        query = payload.get("text")
        if not isinstance(query, str) or not query.strip() or len(query) > 120:
            raise RuntimeError("Search text must be 1-120 characters.")
        url = "https://www.youtube.com/results?search_query=" + quote_plus(query.strip())
        if not webbrowser.open(url, new=2, autoraise=True):
            raise RuntimeError("Windows could not open the YouTube search in the default browser.")
        return {"ok": True, "action": action, "destination": "YouTube search"}
    if action == "open_approved_site":
        site_id = payload.get("site_id")
        local_sites = {"qa_home": "http://127.0.0.1:5200/desktop-control-test.html",
                       "qa_sandbox": "http://127.0.0.1:5200/desktop-control-sandbox.html"}
        if site_id not in local_sites:
            raise RuntimeError("That local QA destination is not approved.")
        webbrowser.open(local_sites[site_id], new=2, autoraise=True)
        return {"ok": True, "action": action, "site_id": site_id}

    if action in {"click_visible", "focus_visible", "type_into_visible"}:
        requested = str(payload.get("target_name") or "").strip()
        if not requested or len(requested) > 120 or SENSITIVE_LABEL.search(requested):
            raise RuntimeError("A safe visible control name is required.")
        deadline = time.monotonic() + 15
        last_error = "No matching visible control was found."
        while time.monotonic() < deadline:
            cancel_check()
            fresh = get_snapshot()
            candidates = [item for item in fresh["targets"] if item["kind"] != "window"
                          and requested.casefold() in item["name"].casefold()]
            if len(candidates) == 1:
                target = candidates[0]
                if action == "type_into_visible" and target["kind"] not in {"text", "search"}:
                    raise RuntimeError("The named visible control is not a text or search field.")
                mapped = {"click_visible": "click_target", "focus_visible": "focus_target",
                          "type_into_visible": "type_into"}[action]
                result = execute_action({"action": mapped, "target_id": target["id"],
                    **({"text": payload.get("text")} if action == "type_into_visible" else {})},
                    type_text=type_text, cancel_check=cancel_check, confirmed_close=confirmed_close,
                    sequence_context=context, snapshot_id=fresh["snapshot_id"],
                    active_window_id=fresh["active_window_id"], focus_target_id=fresh["focused_target_id"])
                latest = get_snapshot()
                context.update(snapshot_id=latest["snapshot_id"], active_window_id=latest["active_window_id"],
                               focus_target_id=latest["focused_target_id"] or target["id"])
                return {"ok": True, "action": action, "target": target["name"],
                        "result": result.get("action", mapped)}
            if len(candidates) > 1:
                names = sorted({item["name"] for item in candidates}, key=str.casefold)
                raise RuntimeError("That visible control name is ambiguous: " + ", ".join(names[:4]))
            time.sleep(0.4)
        raise RuntimeError(last_error)

    snapshot_id = payload.get("snapshot_id", snapshot_id)
    target_id = payload.get("target_id")
    target = _cached_target(snapshot_id, target_id) if target_id else None
    if action in {"switch_window", "minimize_window", "maximize_window", "close_window"}:
        if not target or target["kind"] != "window":
            raise RuntimeError("Choose a current window from the UI Automation list.")
        window = target["wrapper"]
        if action == "switch_window":
            window.set_focus()
            deadline = time.monotonic() + 2
            while _foreground_handle() != target["handle"] and time.monotonic() < deadline:
                cancel_check()
                time.sleep(0.05)
            if _foreground_handle() != target["handle"]:
                raise RuntimeError("Windows did not activate the selected window.")
            return {"ok": True, "action": action, "target": target["label"]}
        if action == "minimize_window":
            window.minimize()
            if not ctypes.windll.user32.IsIconic(target["handle"]):
                raise RuntimeError("Windows did not minimize the selected window.")
            return {"ok": True, "action": action, "target": target["label"]}
        if action == "maximize_window":
            window.maximize()
            if not ctypes.windll.user32.IsZoomed(target["handle"]):
                raise RuntimeError("Windows did not maximize the selected window.")
            return {"ok": True, "action": action, "target": target["label"]}
        if not confirmed_close:
            raise RuntimeError("Closing a window requires the separate close confirmation.")
        window.close()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and ctypes.windll.user32.IsWindow(target["handle"]):
            cancel_check()
            time.sleep(0.1)
        if ctypes.windll.user32.IsWindow(target["handle"]):
            raise RuntimeError("The window is still open; it may have an unsaved-work confirmation. Resolve it yourself.")
        return {"ok": True, "action": action, "target": target["label"], "closed": True}

    if action in {"move_qa_pointer", "click_qa_control"}:
        window = _cached_target(snapshot_id, active_window_id)
        if (window["kind"] != "window" or _foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("Keep the disposable desktop QA window in the foreground.")
        bounds = window["wrapper"].rectangle()
        if action == "move_qa_pointer":
            direction = payload.get("direction")
            delta = {"left": (-80, 0), "right": (80, 0), "up": (0, -80), "down": (0, 80)}.get(direction) if isinstance(direction, str) else None
            if delta is None:
                raise RuntimeError("Choose left, right, up, or down.")
            start = pyautogui.position()
            if not (bounds.left <= start.x < bounds.right and bounds.top <= start.y < bounds.bottom):
                raise RuntimeError("Place the cursor inside the disposable desktop QA window first.")
            x = max(bounds.left, min(bounds.right - 1, start.x + delta[0]))
            y = max(bounds.top, min(bounds.bottom - 1, start.y + delta[1]))
            if (x, y) == (start.x, start.y):
                raise RuntimeError("The cursor is already at the edge of the QA window.")
        else:
            if not target or target["kind"] != "button" or target["handle"] != window["handle"]:
                raise RuntimeError("Choose a visible button from the disposable desktop QA window.")
            wrapper = target["wrapper"]
            rect = wrapper.rectangle()
            label = str(wrapper.element_info.name or "").strip()
            if (label.casefold() not in {"test button", "search", "open chapter"}
                    or not wrapper.is_visible() or not wrapper.is_enabled()
                    or label != target["label"] or label != payload.get("target_name")
                    or [rect.left, rect.top, rect.right, rect.bottom] != target["rect"]):
                raise RuntimeError("The approved button changed. Prepare the action again.")
            matches = [button for button in window["wrapper"].descendants(control_type="Button")
                       if button.is_visible()
                       and str(button.element_info.name or "").strip().casefold() == label.casefold()]
            if len(matches) != 1 or matches[0].element_info != wrapper.element_info:
                raise RuntimeError("The approved button is missing or its name is no longer unique.")
            x, y = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2

        if not (bounds.left <= x < bounds.right and bounds.top <= y < bounds.bottom):
            raise RuntimeError("The approved target is outside the disposable QA window.")
        cancel_check()
        if _foreground_handle() != window["handle"]:
            raise RuntimeError("The desktop QA window lost focus.")
        pyautogui.moveTo(x, y, duration=0.15)
        actual = pyautogui.position()
        if (actual.x, actual.y) != (x, y):
            raise RuntimeError("Windows did not move the cursor to the approved position.")
        if action == "click_qa_control":
            cancel_check()
            hit = Desktop(backend="uia").from_point(x, y)
            if _foreground_handle() != window["handle"] or hit.element_info != wrapper.element_info:
                raise RuntimeError("The approved button is no longer under the cursor.")
            cancel_check()
            pyautogui.click(x, y)
        return {"ok": True, "action": action, "cursor": [x, y]}

    if action in {"click_target", "move_to_target", "focus_target", "type_into", "search"}:
        if not target or target["kind"] == "window":
            raise RuntimeError("Choose a visible control from the UI Automation list.")
        target["wrapper"].set_focus()
        if _foreground_handle() != target["handle"]:
            raise RuntimeError("Windows did not activate the selected control's window.")
        if action in {"focus_target", "type_into", "search"}:
            if action == "focus_target":
                return {"ok": True, "action": action, "target": target["label"]}
            if target["kind"] not in {"text", "search"}:
                raise RuntimeError("Typing is allowed only in a visible text or search control.")
            value = payload.get("text")
            if not isinstance(value, str) or not value or len(value) > 120 or not value.isprintable():
                raise RuntimeError("Text entry must be 1-120 printable characters.")
            type_text(value)
            if action == "search":
                pyautogui.press("enter")
                return {"ok": True, "action": action, "target": target["label"], "submitted": True}
            return {"ok": True, "action": action, "target": target["label"], "typed_characters": len(value)}
        left, top, right, bottom = target["rect"]
        x, y = (left + right) // 2, (top + bottom) // 2
        pyautogui.moveTo(x, y, duration=0.15)
        actual = pyautogui.position()
        if abs(actual.x - x) > 3 or abs(actual.y - y) > 3:
            raise RuntimeError("Windows did not move the real pointer to the selected control.")
        if action == "click_target":
            cancel_check()
            pyautogui.click(x, y)
        return {"ok": True, "action": action, "target": target["label"], "cursor": [actual.x, actual.y]}

    if action == "type":
        value = payload.get("text")
        if not isinstance(value, str) or not value or len(value) > 120 or not value.isprintable():
            raise RuntimeError("Text entry must be 1-120 printable characters.")
        if context.get("launched_app"):
            active_handle = _foreground_handle()
            active_entry = next((item for item in _windows() if item["handle"] == active_handle
                                 and item["app_id"] == context["launched_app"]), None)
            if not active_entry:
                raise RuntimeError("The newly opened approved application is not in the foreground.")
            edits = []
            try:
                for candidate in active_entry["wrapper"].descendants():
                    if candidate.element_info.control_type not in {"Edit", "Document"}:
                        continue
                    if candidate.is_visible() and not candidate.is_password():
                        edits.append(candidate)
            except Exception:
                pass
            if len(edits) != 1:
                raise RuntimeError("I could not uniquely identify the new app's editable document area.")
            edits[0].set_focus()
            focus_label = "newly opened " + SUPPORTED_APPS[context["launched_app"]]
        else:
            active_target = _cached_target(snapshot_id, active_window_id) if active_window_id else None
            focus = _cached_target(snapshot_id, focus_target_id) if focus_target_id else None
            if not active_target or active_target["kind"] != "window" or _foreground_handle() != active_target["handle"]:
                raise RuntimeError("Typing requires the selected window to remain in the foreground.")
            if not focus or focus["kind"] not in {"text", "search"}:
                raise RuntimeError("Typing requires a currently selected text field from the UI Automation snapshot.")
            focus["wrapper"].set_focus()
            focus_label = focus["label"]
        type_text(value)
        return {"ok": True, "action": "type", "target": focus_label, "typed_characters": len(value)}

    if action == "scroll_up" or action == "scroll_down":
        if not target:
            raise RuntimeError("Scroll requires a current visible window target.")
        target["wrapper"].set_focus()
        if _foreground_handle() != target["handle"]:
            raise RuntimeError("Windows did not activate the selected scroll target.")
        if target["kind"] == "window":
            rect = target["wrapper"].rectangle()
            x, y = int((rect.left + rect.right) / 2), int((rect.top + rect.bottom) / 2)
        else:
            left, top, right, bottom = target["rect"]
            x, y = (left + right) // 2, (top + bottom) // 2
        pyautogui.moveTo(x, y, duration=0.1)
        pyautogui.scroll(-4 if action == "scroll_down" else 4, x=x, y=y)
        return {"ok": True, "action": action, "target": target["label"], "cursor": [x, y]}
    if action in {"navigate_back", "navigate_forward"}:
        active_target = _cached_target(snapshot_id, active_window_id) if active_window_id else None
        if not active_target or active_target["kind"] != "window" or active_target["app_id"] not in {"chrome", "edge"}:
            raise RuntimeError("Browser navigation requires a selected Chrome or Edge window.")
        if _foreground_handle() != active_target["handle"]:
            raise RuntimeError("The selected browser window is no longer in the foreground.")
        pyautogui.hotkey("alt", "left" if action == "navigate_back" else "right")
        return {"ok": True, "action": action}
    if action == "keyboard_shortcut":
        active_target = _cached_target(snapshot_id, active_window_id) if active_window_id else None
        if not active_target or active_target["kind"] != "window" or _foreground_handle() != active_target["handle"]:
            raise RuntimeError("A shortcut requires the selected window to remain in the foreground.")
        aliases = {"CTRL+A": ("ctrl", "a"), "CTRL+C": ("ctrl", "c"), "CTRL+L": ("ctrl", "l"),
                   "CTRL+T": ("ctrl", "t"), "CTRL+W": ("ctrl", "w"), "CTRL+SHIFT+T": ("ctrl", "shift", "t"),
                   "CTRL+TAB": ("ctrl", "tab"), "CTRL+SHIFT+TAB": ("ctrl", "shift", "tab"),
                   "ALT+LEFT": ("alt", "left"), "ALT+RIGHT": ("alt", "right"),
                   "ENTER": ("enter",), "ESCAPE": ("esc",)}
        shortcut = str(payload.get("shortcut") or "").upper()
        keys = aliases.get(shortcut)
        if not keys:
            raise RuntimeError("That keyboard shortcut is not allowlisted.")
        pyautogui.hotkey(*keys)
        return {"ok": True, "action": action, "shortcut": shortcut}
    raise RuntimeError("Unsupported or unbound desktop action.")
