"""Research source safety and grounded summaries without external providers."""
from datetime import datetime, timezone

import pytest

from backend.app.services.research import ResearchSource, build_summary, safe_public_url


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "https://localhost/private",
    "http://127.0.0.1/admin",
    "https://user:pass@example.org/path",
    "https://example.org/path?api_key=secret",
])
def test_rejects_nonpublic_or_credential_bearing_citation_urls(url):
    with pytest.raises(ValueError):
        safe_public_url(url, resolve=False)


def test_canonicalizes_public_citation_url():
    assert safe_public_url("HTTPS://Example.ORG:443/a?b=2&utm_source=x#frag", resolve=False) == "https://example.org/a?b=2"


def test_summary_citations_reference_only_returned_source_indices():
    source = ResearchSource(
        title="Open textbook", url="https://openstax.org/books/test", retrieved_at=datetime.now(timezone.utc),
        publisher="openstax.org", excerpt="A bounded excerpt.",
    )
    summary = build_summary("How does it work?", "english", [source])
    assert summary["findings"]
    valid = {citation for finding in summary["findings"] for citation in finding["source_indices"]}
    assert valid == {1}
