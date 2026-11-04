"""Minimal OpenAI-compatible chat-completions provider adapter."""
from __future__ import annotations

import requests

try:
    from .config import LLMConfig
except ImportError:
    from config import LLMConfig


class LLMProviderError(RuntimeError):
    """Safe provider failure without response bodies or secrets."""


class LLMClient:
    def __init__(self, config: LLMConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self.session.post(
                self.config.base_url,
                headers={"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"},
                json={"model": self.config.model, "messages": messages, "temperature": 0.4},
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise LLMProviderError("LLM provider returned an empty or unsupported response.")
            return content.strip()
        except LLMProviderError:
            raise
        except requests.Timeout as exc:
            raise LLMProviderError("LLM provider request timed out.") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            raise LLMProviderError(f"LLM provider returned HTTP {status}.") from exc
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError("LLM provider request failed or returned an invalid response.") from exc
