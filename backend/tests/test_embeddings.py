import json

import httpx
import pytest

from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider


def vector(value=1.0, size=768):
    return [value] + [0.0] * (size - 1)


def provider(handler, *, dimensions=768, retries=0, sleep=lambda _: None):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return GeminiEmbeddingProvider(api_key="test-key", dimensions=dimensions, max_retries=retries, client=client, sleep=sleep), client


def test_batch_request_matches_gemini_contract_and_normalizes_reduced_vectors():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={"embeddings": [{"values": vector(2.0)}, {"values": vector(3.0)}]})

    client_provider, client = provider(handler)
    try:
        result = client_provider.embed_texts(["తెలుగు", "English"], task_type="RETRIEVAL_DOCUMENT")
    finally:
        client.close()
    body = json.loads(captured[0].content)
    assert captured[0].url.path.endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert captured[0].headers["x-goog-api-key"] == "test-key"
    assert body["requests"][0]["model"] == "models/gemini-embedding-001"
    assert body["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert body["requests"][0]["outputDimensionality"] == 768
    assert body["requests"][0]["content"]["parts"][0]["text"] == "తెలుగు"
    assert result[0][0] == pytest.approx(1.0)
    assert sum(x * x for x in result[1]) == pytest.approx(1.0)


def test_batches_are_bounded_and_response_count_is_validated():
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(len(body["requests"]))
        return httpx.Response(200, json={"embeddings": [{"values": vector()} for _ in body["requests"]]})

    embedder, client = provider(handler)
    try:
        assert len(embedder.embed_texts(["text"] * 18, task_type="RETRIEVAL_QUERY")) == 18
    finally:
        client.close()
    assert calls == [16, 2]


@pytest.mark.parametrize("payload", [
    {"embeddings": [{"values": [0.1]}]},
    {"embeddings": [{"values": [float("nan")] * 768}]},
    {"embeddings": [{"values": [float("inf")] * 768}]},
    {"embeddings": [{"values": [0.0] * 768}]},
    {},
])
def test_invalid_vectors_fail_closed(payload):
    embedder, client = provider(lambda request: httpx.Response(200, content=json.dumps(payload, allow_nan=True).encode(), headers={"content-type": "application/json"}))
    try:
        with pytest.raises(EmbeddingError):
            embedder.embed_texts(["secret text"], task_type="RETRIEVAL_QUERY")
    finally:
        client.close()


def test_missing_key_and_permanent_provider_errors_do_not_retry():
    embedder = GeminiEmbeddingProvider(api_key="", max_retries=3)
    with pytest.raises(EmbeddingError, match="not configured"):
        embedder.embed_texts(["text"], task_type="RETRIEVAL_QUERY")
    calls = []
    client_provider, client = provider(lambda request: (calls.append(1), httpx.Response(400))[1], retries=3)
    try:
        with pytest.raises(EmbeddingError):
            client_provider.embed_texts(["private"], task_type="RETRIEVAL_DOCUMENT")
    finally:
        client.close()
    assert len(calls) == 1


def test_transient_errors_retry_with_bounded_backoff():
    calls = []
    delays = []

    def handler(_):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"embeddings": [{"values": vector()}]})

    embedder, client = provider(handler, retries=2, sleep=delays.append)
    embedder._sleep = delays.append
    try:
        embedder.embed_texts(["text"], task_type="RETRIEVAL_QUERY")
    finally:
        client.close()
    assert len(calls) == 2
    assert delays == [0.5]
