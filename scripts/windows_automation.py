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
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote_plus, urlsplit
try:
    from scripts.calculator_math import evaluate_expression
except ImportError:
    from calculator_math import evaluate_expression

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
try:
    from scripts.public_urls import UnsafePublicURL, normalize_public_http_url, verify_public_redirect
except ImportError:
    from public_urls import UnsafePublicURL, normalize_public_http_url, verify_public_redirect


SUPPORTED_APPS = {"notepad": "Notepad", "chrome": "Google Chrome", "edge": "Microsoft Edge", "calculator": "Calculator"}
APPROVED_LINKS = frozenset({"https://www.youtube.com/", "https://chatgpt.com/", "https://www.google.com/"})
DEMO_FORM_VALUES = {"Demo form Name": "Demo Learner", "Demo form Email": "demo.learner@example.test"}
DEMO_FORM_IDS = {"Demo form Name": "qa-demo-name", "Demo form Email": "qa-demo-email"}


def validate_demo_form(fields) -> None:
    if not isinstance(fields, list) or len(fields) != len(DEMO_FORM_VALUES):
        raise RuntimeError("The demo form requires the approved Name and Email fields.")
    seen_labels = set()
    seen_ids = set()
    for field in fields:
        if not isinstance(field, dict):
            raise RuntimeError("Invalid demo form field.")
        label, target_id = field.get("label"), field.get("target_id")
        if (not isinstance(label, str) or label not in DEMO_FORM_VALUES or label in seen_labels
                or field.get("value") != DEMO_FORM_VALUES[label]
                or not isinstance(target_id, str) or not target_id or target_id in seen_ids):
            raise RuntimeError("Only the approved demo fields and synthetic values may be filled.")
        seen_labels.add(label)
        seen_ids.add(target_id)


PROCESS_APPS = {"notepad.exe": "notepad", "chrome.exe": "chrome", "msedge.exe": "edge",
                "calculatorapp.exe": "calculator", "calculator.exe": "calculator"}
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


_ADDRESS_AUTOMATION_IDS = {"omnibox", "addresseditbox", "addressandsearchbox"}
_ADDRESS_NAMES = {"address and search bar", "address bar", "address and search box", "search or enter address"}


def _read_browser_address(entry: dict) -> str:
    """Read only the active Chrome/Edge address control, never page text."""
    if entry.get("app_id") not in {"chrome", "edge"}:
        raise RuntimeError("The foreground application is not a supported browser.")
    candidates = []
    try:
        controls = entry["wrapper"].descendants()
    except Exception:
        controls = []
    for control in controls:
        try:
            info = control.element_info
            control_type = str(info.control_type or "")
            automation_id = str(getattr(info, "automation_id", "") or "").casefold()
            name = str(info.name or "").strip().casefold()
            if control_type not in {"Edit", "ComboBox"}:
                continue
            if automation_id not in _ADDRESS_AUTOMATION_IDS and name not in _ADDRESS_NAMES:
                continue
            if not control.is_visible() or not control.is_enabled() or control.is_password():
                continue
            value = str(control.iface_value.CurrentValue or "").strip()
            if value:
                candidates.append((automation_id in _ADDRESS_AUTOMATION_IDS, value))
        except Exception:
            continue
    if not candidates:
        raise RuntimeError("The browser address bar is not exposed through Windows UI Automation.")
    preferred = [value for exact, value in candidates if exact]
    values = preferred or [value for _, value in candidates]
    if len(set(values)) != 1:
        raise RuntimeError("Windows exposed more than one browser address control.")
    return values[0]


def _foreground_browser_entry() -> dict | None:
    foreground = _foreground_handle()
    return next((entry for entry in _windows()
                 if entry["handle"] == foreground and entry["app_id"] in {"chrome", "edge"}), None)


def _navigate_and_verify(url: str, *, cancel_check, timeout: float = 20.0) -> dict:
    try:
        requested = normalize_public_http_url(url, resolve_dns=True)
    except UnsafePublicURL as exc:
        raise RuntimeError(str(exc)) from exc
    before = None
    try:
        entry = _foreground_browser_entry()
        if entry:
            before = _read_browser_address(entry)
    except RuntimeError:
        before = None
    try:
        dispatched = webbrowser.open(requested, new=2, autoraise=True)
    except (OSError, webbrowser.Error):
        dispatched = False
    if not dispatched:
        raise RuntimeError("Windows could not send the approved website to Chrome or Edge.")

    deadline = time.monotonic() + timeout
    last_url = None
    stable_reads = 0
    last_error = "The browser did not expose a verified public URL."
    while time.monotonic() < deadline:
        cancel_check()
        entry = _foreground_browser_entry()
        if not entry:
            last_error = "Bring the approved Chrome or Edge window to the foreground to verify navigation."
            time.sleep(0.25)
            continue
        try:
            observed = _read_browser_address(entry)
            if observed.casefold().startswith(("chrome-error:", "edge-error:", "about:", "file:")):
                raise RuntimeError("The browser displayed an internal error page instead of the approved website.")
            verified = verify_public_redirect(requested, observed)
        except UnsafePublicURL as exc:
            raise RuntimeError(str(exc)) from exc
        except RuntimeError as exc:
            last_error = str(exc)
            time.sleep(0.25)
            continue
        if before is not None and observed == before and urlsplit(verified).hostname != urlsplit(requested).hostname:
            time.sleep(0.25)
            continue
        if verified == last_url:
            stable_reads += 1
        else:
            last_url = verified
            stable_reads = 1
        if stable_reads >= 2:
            return {"ok": True, "requested_url": requested, "verified_url": verified,
                    "verified_window": entry["id"], "redirected": verified != requested}
        time.sleep(0.35)
    raise RuntimeError(last_error)


def _launch_app(app_id: str, *, cancel_check) -> dict:
    if app_id not in SUPPORTED_APPS:
        raise RuntimeError("Only Notepad, Chrome, Edge, and Calculator can be launched by voice.")
    paths = {
        "notepad": shutil.which("notepad.exe") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "notepad.exe"),
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "calculator": shutil.which("calc.exe") or str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "calc.exe"),
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


def _calculate_in_calculator(expression: str, *, type_text, cancel_check) -> dict:
    try:
        expected = evaluate_expression(expression)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    entry = next((item for item in _windows() if item["app_id"] == "calculator"), None)
    if not entry:
        _launch_app("calculator", cancel_check=cancel_check)
        entry = next((item for item in _windows() if item["app_id"] == "calculator"), None)
    if not entry:
        raise RuntimeError("Calculator did not expose a visible window.")
    cancel_check()
    entry["wrapper"].set_focus()
    if _foreground_handle() != entry["handle"]:
        raise RuntimeError("Calculator did not become the foreground window.")
    displays = []
    for control in entry["wrapper"].descendants():
        try:
            if str(getattr(control.element_info, "automation_id", "") or "") == "CalculatorResults":
                displays.append(control)
        except Exception:
            continue
    if len(displays) != 1 or not displays[0].is_visible():
        raise RuntimeError("Windows could not uniquely identify the Calculator result display.")
    pyautogui.hotkey("ctrl", "a")
    for char in expression:
        cancel_check()
        if char.isspace():
            continue
        if char == "×":
            pyautogui.write("*")
        elif char == "÷":
            pyautogui.write("/")
        else:
            type_text(char)
    cancel_check()
    pyautogui.press("enter")
    deadline = time.monotonic() + 5
    observed_text = ""
    while time.monotonic() < deadline:
        cancel_check()
        try:
            observed_text = str(displays[0].element_info.name or "")
        except Exception:
            observed_text = ""
        numbers = re.findall(r"-?\d[\d,]*(?:\.\d+)?", observed_text)
        if numbers:
            try:
                observed = Decimal(numbers[-1].replace(",", ""))
            except Exception:
                observed = None
            if observed == expected:
                return {"ok": True, "action": "calculate", "verified": True,
                        "verified_result": str(expected), "verified_window": entry["id"]}
        time.sleep(0.15)
    raise RuntimeError("Calculator did not display the expected verified result. Inspect it before retrying.")


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
    if action == "calculate":
        return _calculate_in_calculator(payload.get("text", ""), type_text=type_text, cancel_check=cancel_check)
    if action == "open_named_link":
        url = payload.get("url")
        if not isinstance(url, str):
            raise RuntimeError("A public website URL is required.")
        result = _navigate_and_verify(url, cancel_check=cancel_check)
        context.update(browser_window_id=result["verified_window"], verified_url=result["verified_url"])
        return {"ok": True, "action": action, **result}
    if action == "open_website":
        url = payload.get("url")
        if not isinstance(url, str):
            raise RuntimeError("A public website URL is required.")
        result = _navigate_and_verify(url, cancel_check=cancel_check)
        context.update(browser_window_id=result["verified_window"], verified_url=result["verified_url"])
        return {"ok": True, "action": action, **result}
    if action == "search_web":
        query = payload.get("text")
        if not isinstance(query, str) or not query.strip() or len(query) > 120:
            raise RuntimeError("Search text must be 1-120 characters.")
        url = "https://www.google.com/search?q=" + quote_plus(query.strip())
        result = _navigate_and_verify(url, cancel_check=cancel_check)
        context.update(browser_window_id=result["verified_window"], verified_url=result["verified_url"])
        return {"ok": True, "action": action, "destination": "Google search", **result}
    if action == "search_youtube":
        query = payload.get("text")
        if not isinstance(query, str) or not query.strip() or len(query) > 120:
            raise RuntimeError("Search text must be 1-120 characters.")
        url = "https://www.youtube.com/results?search_query=" + quote_plus(query.strip())
        result = _navigate_and_verify(url, cancel_check=cancel_check)
        context.update(browser_window_id=result["verified_window"], verified_url=result["verified_url"])
        return {"ok": True, "action": action, "destination": "YouTube search", **result}
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
            browser_window_id = context.get("browser_window_id")
            if browser_window_id:
                if fresh["active_window_id"] != browser_window_id or fresh["active_app"] not in {"Google Chrome", "Microsoft Edge"}:
                    raise RuntimeError("The approved browser window lost focus before text entry.")
                browser_entry = next((item for item in _windows() if item["id"] == browser_window_id), None)
                if not browser_entry or _foreground_handle() != browser_entry["handle"]:
                    raise RuntimeError("The approved browser window is no longer in the foreground.")
                try:
                    observed_url = verify_public_redirect(context["verified_url"], _read_browser_address(browser_entry))
                except (UnsafePublicURL, RuntimeError) as exc:
                    raise RuntimeError("The approved browser destination changed before text entry.") from exc
                if observed_url != context["verified_url"]:
                    raise RuntimeError("The browser navigated away from the approved destination.")
            candidates = [item for item in fresh["targets"] if item["kind"] != "window"
                          and requested.casefold() in item["name"].casefold()]
            if len(candidates) == 1:
                target = candidates[0]
                if action == "type_into_visible" and target["kind"] not in {"text", "search"}:
                    raise RuntimeError("The named visible control is not a text or search field.")
                if action == "type_into_visible":
                    text_value = payload.get("text")
                    if not isinstance(text_value, str) or not 1 <= len(text_value) <= 1000 or any(ord(char) < 32 and char not in "\r\n\t" for char in text_value):
                        raise RuntimeError("Text entry must be 1–1000 safe characters.")
                    cached = _cached_target(fresh["snapshot_id"], target["id"])
                    wrapper = cached["wrapper"]
                    try:
                        value_pattern = wrapper.iface_value
                        if (not wrapper.is_enabled() or wrapper.element_info.element.CurrentIsPassword
                                or value_pattern.CurrentIsReadOnly):
                            raise RuntimeError("The selected field is not editable.")
                        old_value = value_pattern.CurrentValue or ""
                    except RuntimeError:
                        raise
                    except Exception:
                        raise RuntimeError("Windows could not verify that the selected field is editable.") from None
                    mode = payload.get("text_mode", "replace")
                    if mode not in {"append", "replace"}:
                        raise RuntimeError("Choose append or replace text mode.")
                    wrapper.set_focus()
                    if _foreground_handle() != cached["handle"] or not wrapper.has_keyboard_focus():
                        raise RuntimeError("Windows could not confirm focus in the approved text field.")
                    if mode == "replace":
                        pyautogui.hotkey("ctrl", "a")
                    elif old_value:
                        pyautogui.hotkey("ctrl", "end")
                    for char in text_value:
                        cancel_check()
                        if _foreground_handle() != cached["handle"]:
                            raise RuntimeError("The approved browser or application lost foreground focus during text entry.")
                        if char in "\r\n":
                            if browser_window_id:
                                pyautogui.hotkey("shift", "enter")
                            else:
                                pyautogui.press("enter")
                        elif char == "\t":
                            pyautogui.press("tab")
                        else:
                            type_text(char)
                    try:
                        final_value = value_pattern.CurrentValue or ""
                    except Exception:
                        raise RuntimeError("Windows could not verify the text entry. Inspect the field before retrying.") from None
                    expected = text_value if mode == "replace" else old_value + text_value
                    if final_value != expected:
                        raise RuntimeError("Windows did not verify the exact text entry. Inspect the field before retrying.")
                    return {"ok": True, "action": action, "target": target["name"],
                            "typed_characters": len(text_value), "verified": True, "submitted": False}
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

    if action == "fill_qa_demo_form":
        fields = payload.get("fields")
        validate_demo_form(fields)
        window = _cached_target(snapshot_id, active_window_id)
        if (window["kind"] != "window" or _foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("Keep the disposable desktop QA window in the foreground.")

        def require_foreground():
            if (_foreground_handle() != window["handle"]
                    or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
                raise RuntimeError("The disposable QA window changed.")

        def resolve_fields():
            edits = window["wrapper"].descendants(control_type="Edit")
            resolved = []
            for field in fields:
                label = field["label"]
                cached = _cached_target(snapshot_id, field["target_id"])
                matches = [edit for edit in edits if edit.is_visible()
                           and str(edit.element_info.name or "").strip() == label]
                if (cached["kind"] != "text" or cached["handle"] != window["handle"] or cached["label"] != label
                        or len(matches) != 1 or matches[0].element_info != cached["wrapper"].element_info):
                    raise RuntimeError("The approved demo form changed. Prepare the action again.")
                edit = matches[0]
                element = edit.element_info.element
                if (element.CurrentAutomationId != DEMO_FORM_IDS[label]
                        or element.CurrentIsPassword or not edit.is_enabled()):
                    raise RuntimeError("The approved demo field is no longer editable.")
                value = edit.iface_value
                if value.CurrentIsReadOnly:
                    raise RuntimeError("The approved demo field is read-only.")
                resolved.append(value)
            return resolved

        # Preflight both controls before the first write. A provider error or
        # Emergency Stop after the first write may leave a partially filled form.
        try:
            resolve_fields()
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("Windows could not access both demo fields. Reopen the QA page and prepare the action again.") from None
        attempted = False
        try:
            for index, field in enumerate(fields):
                value = resolve_fields()[index]
                require_foreground()
                cancel_check()
                if value.CurrentValue == field["value"]:
                    continue
                attempted = True
                value.SetValue(field["value"])
                if value.CurrentValue != field["value"]:
                    raise RuntimeError("Windows did not verify the demo field value.")
            verified = resolve_fields()
            require_foreground()
            cancel_check()
            if any(value.CurrentValue != field["value"] for value, field in zip(verified, fields)):
                raise RuntimeError("Windows did not verify both demo field values.")
        except Exception:
            if attempted:
                raise RuntimeError("The demo form may be partly filled. Inspect both fields before retrying.") from None
            raise
        return {"ok": True, "action": action, "verified_fields": len(fields)}

    if action == "type_qa_text":
        value = payload.get("text")
        if not isinstance(value, str) or not 1 <= len(value) <= 120 or not value.isprintable():
            raise RuntimeError("Text entry must be 1–120 printable characters.")
        window = _cached_target(snapshot_id, active_window_id)
        if (window["kind"] != "window" or _foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("Keep the disposable desktop QA window in the foreground.")
        label = "Permitted text field"
        if (not target or target["kind"] != "text" or target["handle"] != window["handle"]
                or target["label"] != label or payload.get("target_name") != label):
            raise RuntimeError("Choose the Permitted text field in the disposable QA window.")
        wrapper = target["wrapper"]
        fields = [field for field in window["wrapper"].descendants(control_type="Edit")
                  if field.is_visible() and str(field.element_info.name or "").strip() == label]
        if len(fields) != 1 or fields[0].element_info != wrapper.element_info:
            raise RuntimeError("The approved field is missing or its name is no longer unique.")
        if (not wrapper.is_visible() or not wrapper.is_enabled()
                or wrapper.element_info.element.CurrentIsPassword):
            raise RuntimeError("The approved field is no longer editable.")
        # Use the freshly resolved control after confirming its identity.
        try:
            field_value = fields[0].iface_value
            readonly = field_value.CurrentIsReadOnly
        except Exception:
            raise RuntimeError("Windows could not access the approved field for text entry. Prepare the action again.") from None
        if readonly:
            raise RuntimeError("The approved field is read-only.")
        cancel_check()
        if (_foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("The disposable desktop QA window changed before text entry.")
        try:
            field_value.SetValue(value)
            observed = field_value.CurrentValue
        except Exception:
            raise RuntimeError("Windows could not confirm the write. Inspect the approved field before retrying.") from None
        if observed != value:
            raise RuntimeError("Windows did not verify the field value. Inspect the field before retrying.")
        return {"ok": True, "action": action, "target": label, "typed_characters": len(value)}

    if action in {"move_qa_pointer", "click_qa_control"}:
        window = _cached_target(snapshot_id, active_window_id)
        if (window["kind"] != "window" or _foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("Keep the disposable desktop QA window in the foreground.")
        bounds = window["wrapper"].rectangle()
        # Keep moves away from the resize border and the global corner fail-safe.
        left, top, right, bottom = bounds.left + 8, bounds.top + 8, bounds.right - 8, bounds.bottom - 8
        if right <= left or bottom <= top:
            raise RuntimeError("The disposable QA window is too small. Enlarge it and prepare the action again.")
        if action == "move_qa_pointer":
            direction = payload.get("direction")
            delta = {"left": (-80, 0), "right": (80, 0), "up": (0, -80), "down": (0, 80)}.get(direction) if isinstance(direction, str) else None
            if delta is None:
                raise RuntimeError("Choose left, right, up, or down.")
            start = pyautogui.position()
            if not (left <= start.x < right and top <= start.y < bottom):
                raise RuntimeError("Place the cursor inside the disposable desktop QA window first.")
            x = max(left, min(right - 1, start.x + delta[0]))
            y = max(top, min(bottom - 1, start.y + delta[1]))
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

        if not (left <= x < right and top <= y < bottom):
            raise RuntimeError("The approved target is outside the disposable QA window.")
        cancel_check()
        if _foreground_handle() != window["handle"]:
            raise RuntimeError("The desktop QA window lost focus.")
        pyautogui.moveTo(x, y, duration=0.15)
        actual = pyautogui.position()
        if (actual.x, actual.y) != (x, y):
            raise RuntimeError("Windows did not move the cursor to the approved position.")
        if (_foreground_handle() != window["handle"]
                or not _is_pointer_qa_window(window["app_id"], window["wrapper"])):
            raise RuntimeError("The desktop QA window changed during pointer movement.")
        if action == "click_qa_control":
            cancel_check()
            hit = Desktop(backend="uia").from_point(x, y)
            current = wrapper.rectangle()
            current_pointer = pyautogui.position()
            if (_foreground_handle() != window["handle"]
                    or not _is_pointer_qa_window(window["app_id"], window["wrapper"])
                    or hit.element_info != wrapper.element_info
                    or not wrapper.is_visible() or not wrapper.is_enabled()
                    or str(wrapper.element_info.name or "").strip() != label
                    or [current.left, current.top, current.right, current.bottom] != target["rect"]
                    or (current_pointer.x, current_pointer.y) != (x, y)):
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
        if not isinstance(value, str) or not value or len(value) > 1000 or any(ord(char) < 32 and char not in "\r\n\t" for char in value):
            raise RuntimeError("Text entry must contain 1–1000 safe characters.")
        editable = None
        previous = ""
        required_foreground = None
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
            editable = edits[0]
            required_foreground = active_entry["handle"]
            try:
                pattern = editable.iface_value
                if not editable.is_enabled() or editable.element_info.element.CurrentIsPassword or pattern.CurrentIsReadOnly:
                    raise RuntimeError("The new app document is not editable.")
                previous = pattern.CurrentValue or ""
            except RuntimeError:
                raise
            except Exception:
                raise RuntimeError("Windows could not verify the new app document is editable.") from None
            editable.set_focus()
            focus_label = "newly opened " + SUPPORTED_APPS[context["launched_app"]]
        else:
            active_target = _cached_target(snapshot_id, active_window_id) if active_window_id else None
            focus = _cached_target(snapshot_id, focus_target_id) if focus_target_id else None
            if not active_target or active_target["kind"] != "window" or _foreground_handle() != active_target["handle"]:
                raise RuntimeError("Typing requires the selected window to remain in the foreground.")
            if not focus or focus["kind"] not in {"text", "search"}:
                raise RuntimeError("Typing requires a currently selected text field from the UI Automation snapshot.")
            focus["wrapper"].set_focus()
            required_foreground = active_target["handle"]
            if _foreground_handle() != required_foreground or not focus["wrapper"].has_keyboard_focus():
                raise RuntimeError("Windows could not confirm focus in the selected text field.")
            focus_label = focus["label"]
        for char in value:
            cancel_check()
            if required_foreground is not None and _foreground_handle() != required_foreground:
                raise RuntimeError("The approved Notepad window lost foreground focus during text entry.")
            if char in "\r\n":
                pyautogui.press("enter")
            elif char == "\t":
                pyautogui.press("tab")
            else:
                type_text(char)
        if editable is not None:
            try:
                observed = editable.iface_value.CurrentValue or ""
            except Exception:
                raise RuntimeError("Windows could not verify the Notepad text. Inspect the document before retrying.") from None
            if observed != previous + value:
                raise RuntimeError("Windows did not verify the exact Notepad text. Inspect the document before retrying.")
            return {"ok": True, "action": "type", "target": focus_label,
                    "typed_characters": len(value), "verified": True}
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
