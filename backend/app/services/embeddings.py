"""Gemini text embedding adapter with bounded batches and safe retries."""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Sequence

import httpx

from backend.app.config import get_settings, is_placeholder_secret


class EmbeddingError(RuntimeError):
    """Safe provider/configuration error; contains no input or credential data."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class GeminiEmbeddingProvider:
    MODEL = "gemini-embedding-001"
    BATCH_SIZE = 16
    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        settings = get_settings()
        configured_embedding_key = settings.gemini_embedding_api_key
        if is_placeholder_secret(configured_embedding_key):
            configured_embedding_key = settings.gemini_api_key
        self.api_key = api_key if api_key is not None else configured_embedding_key
        self.model = model if model is not None else settings.gemini_embedding_model
        self.dimensions = dimensions if dimensions is not None else settings.gemini_embedding_dimensions
        self.timeout = timeout if timeout is not None else settings.embedding_timeout_seconds
        self.max_retries = settings.embedding_max_retries if max_retries is None else max_retries
        self._client = client
        self._sleep = sleep
        if self.model != self.MODEL:
            raise EmbeddingError("Configured embedding model is unsupported by this vector schema")
        if self.dimensions != 768:
            raise EmbeddingError("Configured embedding dimensions do not match the vector schema", status_code=503)
        if not math.isfinite(self.timeout) or self.timeout <= 0 or not 0 <= self.max_retries <= 5:
            raise EmbeddingError("Embedding timeout or retry configuration is invalid", status_code=503)

    def _validate_vector(self, values: object) -> list[float]:
        if not isinstance(values, list) or len(values) != self.dimensions:
            raise EmbeddingError("Embedding provider returned an invalid vector dimension")
        vector: list[float] = []
        for value in values:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise EmbeddingError("Embedding provider returned invalid numeric values")
            vector.append(float(value))
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0 or not math.isfinite(norm):
            raise EmbeddingError("Embedding provider returned an empty vector")
        return [value / norm for value in vector]

    def embed_texts(self, texts: Sequence[str], *, task_type: str) -> list[list[float]]:
        if task_type not in {"RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"}:
            raise ValueError("Unsupported embedding task")
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingError("Embedding input must contain non-empty text")
        if is_placeholder_secret(self.api_key):
            raise EmbeddingError("Gemini embedding API key is not configured", status_code=503)
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), self.BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[offset : offset + self.BATCH_SIZE], task_type))
        return vectors

    def _embed_batch(self, texts: Sequence[str], task_type: str) -> list[list[float]]:
        body = {
            "requests": [
                {
                    "model": f"models/{self.model}",
                    "content": {"parts": [{"text": text}]},
                    "taskType": task_type,
                    "outputDimensionality": self.dimensions,
                }
                for text in texts
            ]
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents"
        client = self._client or httpx.Client(timeout=self.timeout)
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    response = client.post(url, headers={"x-goog-api-key": self.api_key}, json=body, timeout=self.timeout)
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt < self.max_retries:
                        self._sleep(min(0.5 * (2**attempt), 4.0))
                        continue
                    raise EmbeddingError("Gemini embedding provider is unavailable") from None
                if response.status_code in self.RETRYABLE_STATUS and attempt < self.max_retries:
                    self._sleep(min(0.5 * (2**attempt), 4.0))
                    continue
                if response.status_code >= 400:
                    raise EmbeddingError("Gemini embedding provider rejected the request")
                try:
                    data = response.json()
                    embeddings = data["embeddings"]
                    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                        raise ValueError
                    if any(not isinstance(item, dict) for item in embeddings):
                        raise ValueError
                    return [self._validate_vector(item.get("values")) for item in embeddings]
                except (ValueError, TypeError, KeyError, AttributeError):
                    raise EmbeddingError("Gemini embedding provider returned an invalid response") from None
            raise EmbeddingError("Gemini embedding provider failed")
        finally:
            if self._client is None:
                client.close()
