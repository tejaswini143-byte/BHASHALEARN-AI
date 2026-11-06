"""Application settings loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BHASHALEARN AI API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/bhashalearn"
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 30
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    document_storage_dir: str = "backend/storage/documents"
    document_max_upload_bytes: int = 10 * 1024 * 1024
    document_max_pages: int = 100
    document_max_extracted_characters: int = 2_000_000
    document_max_filename_length: int = 255

    model_config = SettingsConfigDict(
        env_prefix="BHASHALEARN_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
