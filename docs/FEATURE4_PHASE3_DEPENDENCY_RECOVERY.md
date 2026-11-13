# Feature 4 Phase 3 — Windows backend test dependency recovery

## Root cause
The observed 34 pytest **collection** errors occurred under global Python 3.13, before test bodies executed. The traceback reports missing `pgvector`, `argon2` (provided by `argon2-cffi`), and `pyautogui`. These are environment problems, not proof of 34 application defects.

The existing `backend/requirements.txt` already lists `pgvector` and `argon2-cffi`. The Windows desktop helper imports `pyautogui` and `pywinauto` at module import time, so desktop-specific test collection needs optional dependencies too.

## Recommended commands (Windows CMD; run from repository root)
```bat
cd /d "C:\Users\Tejaswini\BHASHALEARN-INT26\_integration_rc_20261109"
git fetch origin
git switch fix/feature4-phase3-backend-dependency-qa-20261113
"C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe" -m pip install -r backend/requirements-desktop.txt
"C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe" -m pip check
"C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe" -m pytest -p no:cacheprovider -q backend/tests/test_feature4_visual_lessons.py
"C:\Users\Tejaswini\bhashalearn-safe-venv\Scripts\python.exe" -m pytest -p no:cacheprovider -q backend/tests
```

If the existing safe virtual environment is unavailable, create a new environment outside the protected checkout:
```bat
py -3.13 -m venv "%USERPROFILE%\bhashalearn-feature4-venv"
"%USERPROFILE%\bhashalearn-feature4-venv\Scripts\python.exe" -m pip install --upgrade pip
"%USERPROFILE%\bhashalearn-feature4-venv\Scripts\python.exe" -m pip install -r backend/requirements-desktop.txt
```

The `-p no:cacheprovider` flag avoids writing `.pytest_cache` to the access-restricted checkout. A Starlette/httpx deprecation warning is not itself a test failure.

## Limits
This change documents and declares missing dependencies; it cannot install packages on the user's Windows machine via GitHub. The Python tests and live desktop automation remain unverified until executed on that machine. Keep API keys in local environment files, not Git.
