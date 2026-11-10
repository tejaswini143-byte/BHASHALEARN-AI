"""Application settings loaded from environment variables."""
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_placeholder_secret(value: str | None) -> bool:
    """Return whether a credential is empty or an example/template value."""
    normalized = (value or "").strip().casefold()
    return (
        not normalized
        or normalized in {"replace_me", "your_actual_key"}
        or normalized.startswith(("replace-", "replace_", "your-", "your_", "<"))
    )


class Settings(BaseSettings):
    app_name: str = "BHASHALEARN AI API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = ""  # Require BHASHALEARN_DATABASE_URL for database access.
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 30
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = 768
    brave_search_api_key: str = ""
    research_requests_per_minute: int = Field(default=10, ge=1, le=60)
    embedding_chunk_size: int = Field(default=1000, ge=1, le=10000)
    embedding_chunk_overlap: int = Field(default=150, ge=0, le=9999)
    embedding_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    embedding_max_retries: int = Field(default=2, ge=0, le=5)
    document_storage_dir: str = "backend/storage/documents"
    document_max_upload_bytes: int = 10 * 1024 * 1024
    document_max_pages: int = 100
    document_max_extracted_characters: int = 2_000_000
    document_max_filename_length: int = 255
    assistant_token_encryption_key: str = ""
    assistant_public_base_url: str = ""
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    assistant_google_live_enabled: bool = False
    assistant_live_operations_enabled: bool = False
    twilio_live_calls_enabled: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_verify_service_sid: str = ""
    twilio_status_callback_url: str = ""
    twilio_allowed_destination_prefixes: str = ""
    assistant_max_calls_per_day: int = Field(default=3, ge=1, le=20)

    model_config = SettingsConfigDict(
        env_prefix="BHASHALEARN_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_embedding_chunk_settings(self):
        if self.embedding_chunk_overlap >= self.embedding_chunk_size:
            raise ValueError("Embedding chunk overlap must be smaller than chunk size")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
