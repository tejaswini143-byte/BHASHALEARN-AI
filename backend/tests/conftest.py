"""Keep automated tests isolated from developer credentials and .env files."""

import pytest


@pytest.fixture(autouse=True)
def isolate_settings_from_project_dotenv(monkeypatch):
    from backend.app.config import Settings, get_settings

    # Tests must opt into provider credentials through their own monkeypatches.
    # Loading the repository .env here can unexpectedly make a test call a live
    # provider and makes results depend on whoever runs the suite.
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    for name in (
        "BHASHALEARN_GEMINI_API_KEY",
        "BHASHALEARN_GEMINI_EMBEDDING_API_KEY",
        "BHASHALEARN_BRAVE_SEARCH_API_KEY",
        "GNANI_API_KEY",
        "BHASHALEARN_TWILIO_ACCOUNT_SID",
        "BHASHALEARN_TWILIO_AUTH_TOKEN",
        "BHASHALEARN_TWILIO_VERIFY_SERVICE_SID",
        "BHASHALEARN_GOOGLE_OAUTH_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
