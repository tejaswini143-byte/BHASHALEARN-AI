from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://bhasha:bhasha@localhost:55432/bhasha"
    jwt_secret: str = "development-only-change-me"
    app_env: str = "development"
    frontend_origin: str = "http://localhost:5174"
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    sip_outbound_trunk_id: str = ""
    sip_caller_id: str = ""
    gnani_api_key: str = ""
    gnani_stt_url: str = "https://api.vachana.ai/stt/v3"
    gnani_tts_url: str = "https://api.vachana.ai/api/v1/tts/inference"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    allow_test_calls: bool = False


settings = Settings()

