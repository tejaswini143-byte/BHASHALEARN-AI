# Windows desktop control

The local Windows companion provides opt-in UI Automation and mouse/keyboard
actions for the BHASHALEARN desktop assistant. It binds to `127.0.0.1` only and
does not expose a remote-control service.

## Start and connect

From the integration worktree, install the desktop requirements into its
isolated `.venv` and start the companion:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r scripts\requirements-desktop.txt
& .\scripts\start_desktop_companion.ps1
```

Keep the companion window open. Open BHASHALEARN locally, connect the
Desktop Control panel, and use **Enable Control** before interpreting or
executing a command. The panel shows the proposed action; execution requires
an explicit confirmation. Closing a window has an additional confirmation.
**Emergency Stop** disables the companion and cancels remaining sequence
steps.

The current allowlist includes Notepad, Chrome, Edge, HTTPS navigation,
Google/YouTube search, visible UI Automation targets, window focus/minimize/
maximize/close, scrolling, and a small keyboard-shortcut set. Arbitrary shell
commands, private document titles, editable values, password controls, and
unrelated page labels are not sent to the planner. Typing is limited to
explicitly dictated printable text and a uniquely selected field.

## Voice and provider requirements

Desktop intent uses the authenticated BHASHALEARN backend and Gemini plan
validator. Browser speech recognition must provide a Gnani Prisma transcript
before the user confirms an action. A live voice turn also requires an active
student session and valid Gnani/Gemini provider configuration. The companion
does not start recording automatically; microphone capture begins only from an
explicit user control.

## Checks

Run the focused backend tests and frontend checks from the repository:

```powershell
& .\.venv\Scripts\python.exe -m pytest backend\tests\test_desktop_commands.py backend\tests\test_desktop_companion.py backend\tests\test_windows_automation.py -p no:cacheprovider
Push-Location frontend
npm test
npm run build
Pop-Location
```

The 2026-11-12 local verification and its remaining limits are recorded in
[`TEST-EVIDENCE.md`](TEST-EVIDENCE.md). Real desktop interaction is verified
only for the safe actions listed there; voice-to-provider execution and a
full-window close remain unverified.
