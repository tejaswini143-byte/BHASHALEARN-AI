"""Environment-backed configuration for the POC-03 LLM provider."""
from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(RuntimeError):
    """Safe configuration error that never includes credential values."""


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1/chat/completions"
    model: str = "gpt-4o-mini"
    timeout_seconds: int = 45

    @classmethod
    def from_env(cls) -> "LLMConfig":
        key = os.getenv("LLM_API_KEY", "").strip()
        if not key or key in {"replace_me", "YOUR_ACTUAL_KEY"}:
            raise ConfigurationError("Set LLM_API_KEY in the POC-03 local .env file.")
        url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/chat/completions").strip()
        if not url.startswith("https://"):
            raise ConfigurationError("LLM_BASE_URL must use HTTPS.")
        model = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise ConfigurationError("LLM_MODEL must not be empty.")
        try:
            timeout = int(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
        except ValueError as exc:
            raise ConfigurationError("LLM_TIMEOUT_SECONDS must be an integer.") from exc
        if timeout <= 0:
            raise ConfigurationError("LLM_TIMEOUT_SECONDS must be positive.")
        return cls(key, url, model, timeout)
