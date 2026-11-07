"""Explicit test-only API entrypoint with deterministic local embeddings."""
from __future__ import annotations

from backend.app.api.documents import get_embedding_provider
from backend.app.main import create_app


class DeterministicEmbeddingProvider:
    model = "gemini-embedding-001"
    dimensions = 768
    BATCH_SIZE = 16

    def embed_texts(self, texts: list[str], *, task_type: str) -> list[list[float]]:
        if task_type not in {"RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"}:
            raise ValueError("Unsupported test embedding task")
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append([1.0] + [0.0] * 767 if "telugu" in lowered or "fraction" in lowered else [0.0, 1.0] + [0.0] * 766)
        return vectors


app = create_app()
app.dependency_overrides[get_embedding_provider] = DeterministicEmbeddingProvider
