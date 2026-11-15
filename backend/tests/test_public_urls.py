import pytest

from scripts.public_urls import UnsafePublicURL, normalize_public_http_url, verify_public_redirect


@pytest.mark.parametrize(("source", "expected"), [
    ("github.com", "https://github.com/"),
    ("www.google.com/search?q=hello", "https://www.google.com/search?q=hello"),
    ("http://example.org/path?q=a%20b", "http://example.org/path?q=a%20b"),
])
def test_public_url_normalization(source, expected):
    assert normalize_public_http_url(source) == expected


@pytest.mark.parametrize("source", [
    "javascript:alert(1)", "file:///C:/Windows/win.ini", "http://localhost/",
    "http://127.0.0.1/", "http://10.0.0.1/", "http://192.168.1.1/",
    "http://2130706433/", "https://user:pass@example.com/",
    "https://example.com/?access_token=secret", "https://example.local/",
])
def test_unsafe_or_nonpublic_urls_are_rejected(source):
    with pytest.raises(UnsafePublicURL):
        normalize_public_http_url(source)


def test_private_dns_answer_is_rejected(monkeypatch):
    monkeypatch.setattr("scripts.public_urls.socket.getaddrinfo", lambda *args, **kwargs: [
        (2, 1, 6, "", ("127.0.0.1", 443)),
    ])
    with pytest.raises(UnsafePublicURL, match="private or reserved"):
        normalize_public_http_url("https://example.com", resolve_dns=True)


def test_redirect_must_remain_public_and_may_not_downgrade_https(monkeypatch):
    monkeypatch.setattr("scripts.public_urls.socket.getaddrinfo", lambda *args, **kwargs: [
        (2, 1, 6, "", ("93.184.216.34", 443)),
    ])
    assert verify_public_redirect("https://example.com", "https://example.com/next") == "https://example.com/next"
    with pytest.raises(UnsafePublicURL, match="exact approved public host"):
        verify_public_redirect("https://example.com", "https://www.example.com/")
    with pytest.raises(UnsafePublicURL, match="insecure HTTP"):
        verify_public_redirect("https://example.com", "http://example.com/")
    with pytest.raises(UnsafePublicURL):
        verify_public_redirect("https://example.com", "http://127.0.0.1/")
