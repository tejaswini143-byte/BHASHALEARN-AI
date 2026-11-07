"""Application settings loaded from environment variables."""
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BHASHALEARN AI API"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    database_url: str = ""  # Require BHASHALEARN_DATABASE_URL for database access.
    jwt_secret_key: str = ""
    access_token_expire_minutes: int = 30
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_embedding_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimensions: int = 768
    embedding_chunk_size: int = Field(default=1000, ge=1, le=10000)
    embedding_chunk_overlap: int = Field(default=150, ge=0, le=9999)
    embedding_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    embedding_max_retries: int = Field(default=2, ge=0, le=5)
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

    @model_validator(mode="after")
    def validate_embedding_chunk_settings(self):
        if self.embedding_chunk_overlap >= self.embedding_chunk_size:
            raise ValueError("Embedding chunk overlap must be smaller than chunk size")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
