import pytest
from fastapi import HTTPException

from backend.app.services import desktop_commands


def test_gemini_desktop_intent_is_strictly_validated(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"center","text":null}')
    action = desktop_commands.interpret_desktop_command("Move the cursor to the center")
    assert action.action == "center"
    assert action.text is None


def test_ambiguous_unsupported_action_is_rejected(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"unsupported","text":null}')
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Do whatever is needed")
    assert error.value.status_code == 422


def test_sensitive_transcript_never_reaches_gemini(monkeypatch):
    called = False
    def forbidden(*_):
        nonlocal called
        called = True
        return '{}'
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", forbidden)
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Type my password hunter2")
    assert error.value.status_code == 422
    assert not called


def test_type_text_is_parsed_locally_and_never_sent_to_gemini(monkeypatch):
    called = False
    def forbidden(*_):
        nonlocal called
        called = True
        raise AssertionError("dictated field text must stay local")
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", forbidden)
    action = desktop_commands.interpret_desktop_command("Type hello BHASHALEARN")
    assert action.action == "type"
    assert action.text == "hello BHASHALEARN"
    assert not called
    telugu = desktop_commands.interpret_desktop_command("Type నమస్కారం")
    assert telugu.action == "type"
    assert telugu.text == "నమస్కారం"


def test_opening_approved_apps_and_https_sites_is_structured(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply",
                        lambda *_: '{"action":"open_app","app_id":"notepad"}')
    plan = desktop_commands.interpret_desktop_command("Open Notepad")
    assert plan.action == "open_app" and plan.app_id == "notepad"

    monkeypatch.setattr(desktop_commands, "generate_tutor_reply",
                        lambda *_: '{"action":"open_website","url":"https://chatgpt.com"}')
    plan = desktop_commands.interpret_desktop_command("Open ChatGPT")
    assert plan.action == "open_website" and plan.url == "https://chatgpt.com"


def test_compound_notepad_dictation_stays_local_and_is_planned_as_sequence(monkeypatch):
    captured = []
    def fake(_instruction, history):
        captured.append(history[0]["content"])
        return ('{"action":"sequence","steps":[{"action":"open_app","app_id":"notepad"},'
                '{"action":"type","text":"[LOCAL_DICTATION]"}]}')
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", fake)
    plan = desktop_commands.interpret_desktop_command("Open Notepad and type BHASHALEARN AI")
    assert [step.action for step in plan.steps] == ["open_app", "type"]
    assert plan.steps[1].text == "BHASHALEARN AI"
    assert "BHASHALEARN AI" not in captured[0]


def test_unbound_notepad_type_into_is_bound_only_after_explicit_open_step(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: (
        '{"action":"sequence","steps":[{"action":"open_app","app_id":"notepad"},'
        '{"action":"type_into","text":"[LOCAL_DICTATION]"}]}'
    ))
    plan = desktop_commands.interpret_desktop_command("Open Notepad and type BHASHALEARN AI")
    assert [step.action for step in plan.steps] == ["open_app", "type"]
    assert plan.steps[1].text == "BHASHALEARN AI"

    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: (
        '{"action":"sequence","steps":[{"action":"type_into","text":"[LOCAL_DICTATION]"}]}'
    ))
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Open Notepad and type BHASHALEARN AI")
    assert error.value.status_code == 502


def test_youtube_search_query_is_redacted_and_kept_local(monkeypatch):
    captured = []
    def fake(_instruction, history):
        captured.append(history[0]["content"])
        return '{"action":"search_youtube","text":"[LOCAL_DICTATION]"}'
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", fake)
    plan = desktop_commands.interpret_desktop_command("Open YouTube and search Python tutorials")
    assert plan.action == "search_youtube"
    assert plan.text == "Python tutorials"
    assert "Python tutorials" not in captured[0]


def test_first_link_must_match_actual_uia_order(monkeypatch):
    targets = [
        {"id": "first", "role": "hyperlink", "name": "Introduction", "kind": "link"},
        {"id": "second", "role": "hyperlink", "name": "Tutorials", "kind": "link"},
    ]
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply",
                        lambda *_: '{"action":"click_target","target_id":"first"}')
    plan = desktop_commands.interpret_desktop_command("Click the first link", targets)
    assert plan.action == "click_target" and plan.target_id == "first"

    monkeypatch.setattr(desktop_commands, "generate_tutor_reply",
                        lambda *_: '{"action":"click_target","target_id":"second"}')
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Click the first link", targets)
    assert error.value.status_code == 422


def test_unsafe_urls_apps_and_shortcuts_are_rejected():
    with pytest.raises(ValueError):
        desktop_commands.DesktopAction(action="open_website", url="javascript:alert(1)")
    with pytest.raises(ValueError):
        desktop_commands.DesktopAction(action="open_website", url="https://user@example.com")
    with pytest.raises(ValueError):
        desktop_commands.DesktopAction(action="open_app", app_id="powershell")
    with pytest.raises(ValueError):
        desktop_commands.DesktopAction(action="keyboard_shortcut", shortcut="WIN+R")


TARGETS = [
    {"id": "login", "role": "button", "name": "Login button", "kind": "button"},
    {"id": "chapter-one", "role": "button", "name": "Open chapter", "kind": "button"},
    {"id": "chapter-two", "role": "button", "name": "Open chapter", "kind": "button"},
    {"id": "qa-navigation-link", "role": "link", "name": "Navigate to the approved QA destination", "kind": "link"},
    {"id": "query", "role": "searchbox", "name": "Search field", "kind": "search"},
    {"id": "answer", "role": "textbox", "name": "Permitted text field", "kind": "text"},
]
SITES = {
    "qa_home": "http://127.0.0.1:5201/desktop-control-test.html",
    "qa_sandbox": "http://127.0.0.1:5201/desktop-control-sandbox.html",
}


def test_natural_multi_step_request_maps_to_exact_semantic_target(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"sequence","steps":[{"action":"right"},{"action":"click_target","target_id":"login"}]}')
    plan = desktop_commands.interpret_desktop_command("Hey, move right and click the Login button", TARGETS, SITES)
    assert plan.action == "sequence"
    assert [step.action for step in plan.steps] == ["right", "click_target"]
    assert plan.steps[1].target_id == "login"


def test_duplicate_semantic_targets_return_clarification(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click_target","target_id":"chapter-one"}')
    plan = desktop_commands.interpret_desktop_command("Open chapter", TARGETS, SITES)
    assert plan.action == "clarify"
    assert "2 buttons named Open chapter" in plan.clarification


def test_generic_gemini_click_is_bound_to_explicit_semantic_target(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click"}')
    plan = desktop_commands.interpret_desktop_command("Click the Login button", TARGETS, SITES)
    assert plan.action == "click_target"
    assert plan.target_id == "login"


def test_exact_qa_navigation_command_binds_generic_click_to_named_link(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click"}')
    plan = desktop_commands.interpret_desktop_command(
        "Click the link named Navigate to the approved QA destination.", TARGETS, SITES,
    )
    assert plan.action == "click_target"
    assert plan.target_id == "qa-navigation-link"


def test_click_target_cannot_override_the_named_element(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click_target","target_id":"qa-login-button"}')
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command(
            "Click the link named Navigate to the approved QA destination.", TARGETS, SITES,
        )
    assert error.value.status_code == 422
    assert "different element" in error.value.detail


def test_unbound_gemini_click_is_rejected(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click"}')
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Click", TARGETS, SITES)
    assert error.value.status_code == 422
    assert "unbound click was blocked" in error.value.detail


def test_isolated_qa_preview_port_is_allowlisted(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"open_approved_site","site_id":"qa_sandbox"}')
    sites = {"qa_sandbox": "http://127.0.0.1:5202/desktop-control-sandbox.html"}
    plan = desktop_commands.interpret_desktop_command("Open the approved QA sandbox", TARGETS, sites)
    assert plan.action == "open_approved_site"
    assert plan.site_id == "qa_sandbox"


def test_current_qa_preview_port_5203_is_allowlisted(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"open_approved_site","site_id":"qa_sandbox"}')
    sites = {"qa_sandbox": "http://127.0.0.1:5203/desktop-control-sandbox.html"}
    plan = desktop_commands.interpret_desktop_command("Open the approved QA sandbox", TARGETS, sites)
    assert plan.action == "open_approved_site"
    assert plan.site_id == "qa_sandbox"


def test_generic_gemini_click_on_duplicate_target_requests_clarification(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click"}')
    plan = desktop_commands.interpret_desktop_command("Click Open chapter", TARGETS, SITES)
    assert plan.action == "clarify"
    assert "Which one" in plan.clarification


def test_dictated_text_is_redacted_before_gemini_and_restored_locally(monkeypatch):
    captured = []
    def fake(instruction, history):
        captured.append(history[0]["content"])
        return '{"action":"type_into","target_id":"answer","text":"[LOCAL_DICTATION]"}'
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", fake)
    plan = desktop_commands.interpret_desktop_command('Type "fraction answer" into the permitted text field', TARGETS, SITES)
    assert plan.action == "type_into"
    assert plan.text == "fraction answer"
    assert "fraction answer" not in captured[0]
    assert "[DICTATED TEXT REDACTED]" in captured[0]


def test_prisma_trailing_dictation_binds_to_the_uniquely_focused_field(monkeypatch):
    captured = []
    def fake(instruction, history):
        captured.append(history[0]["content"])
        return ('{"action":"sequence","steps":[{"action":"focus_target","target_id":"answer"},'
                '{"action":"type","text":"[LOCAL_DICTATION]"},{"action":"scroll_down"}]}')
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", fake)
    transcript = 'Yes, exactly. Scroll down, focus the Permitted text field, then type "QA sequence verified".'
    plan = desktop_commands.interpret_desktop_command(transcript, TARGETS, SITES)
    assert [step.action for step in plan.steps] == ["focus_target", "type_into", "scroll_down"]
    assert plan.steps[1].target_id == "answer"
    assert plan.steps[1].text == "QA sequence verified"
    assert "QA sequence verified" not in captured[0]
    assert "[DICTATED TEXT REDACTED]" in captured[0]


def test_prisma_trailing_dictation_without_one_focused_field_is_rejected_before_gemini(monkeypatch):
    called = False
    def forbidden(*_):
        nonlocal called
        called = True
        raise AssertionError("unbound dictated text must not reach Gemini")
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", forbidden)
    with pytest.raises(HTTPException):
        desktop_commands.interpret_desktop_command('Scroll down, then type "QA sequence verified"', TARGETS, SITES)
    assert not called


def test_search_query_is_redacted_and_bound_to_search_target(monkeypatch):
    captured = []
    def fake(instruction, history):
        captured.append(history[0]["content"])
        return '{"action":"search","target_id":"query","text":"[LOCAL_DICTATION]"}'
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", fake)
    plan = desktop_commands.interpret_desktop_command("Search for fraction addition in this site", TARGETS, SITES)
    assert plan.action == "search"
    assert plan.text == "fraction addition"
    assert "fraction addition" not in captured[0]


def test_unknown_target_and_non_allowlisted_site_are_rejected(monkeypatch):
    monkeypatch.setattr(desktop_commands, "generate_tutor_reply", lambda *_: '{"action":"click_target","target_id":"elsewhere"}')
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Click the Login button", TARGETS, SITES)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException) as error:
        desktop_commands.interpret_desktop_command("Open the site", TARGETS, {"site": "https://example.com"})
    assert error.value.status_code == 422
