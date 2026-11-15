from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[1] / ".env", extra="ignore")
    database_url: str = "postgresql+psycopg://bhasha:bhasha@localhost:55432/bhasha"
    jwt_secret: str = "development-only-change-me"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5174"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    sip_outbound_trunk_id: str = ""
    sip_caller_id: str = ""
    verified_test_numbers: str = ""
    max_calls_per_day: int = 3
    call_start_hour: int = 9
    call_end_hour: int = 20
    gnani_api_key: str = ""
    gnani_stt_url: str = "https://api.vachana.ai/stt/v3"
    gnani_tts_url: str = "https://api.vachana.ai/api/v1/tts/inference"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    livekit_agent_name: str = "bhashalearn-deadline-reminder"
    allow_test_calls: bool = False


settings = Settings()

