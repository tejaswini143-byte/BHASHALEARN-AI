"""URL rules shared by Gemini plan validation and the Windows companion."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import parse_qsl, urlsplit, urlunsplit


_NUMERIC_HOST = re.compile(r"^(?:(?:0x[0-9a-f]+)|(?:[0-9]+))(?:\.(?:(?:0x[0-9a-f]+)|(?:[0-9]+)))*$", re.I)
_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.I)
_SENSITIVE_QUERY_KEY = re.compile(r"(?:pass(?:word|code)?|secret|token|api[-_]?key|auth(?:orization)?|session|otp|one[-_]?time|credential|access[-_]?code)", re.I)
_LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".home", ".lan", ".test", ".invalid", ".example", ".onion")


class UnsafePublicURL(ValueError):
    """The destination is malformed, local, private, or credential-bearing."""


def normalize_public_http_url(value: str, *, resolve_dns: bool = False) -> str:
    """Return a canonical public HTTP(S) URL, optionally checking DNS answers.

    Domain-only input defaults to HTTPS. Nonstandard ports, credentials, local
    names, private IP literals, and credential-like query/fragment fields fail
    closed. DNS checks are reserved for the Windows companion immediately
    before dispatch and again when verifying the final browser URL.
    """
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise UnsafePublicURL("The website URL is empty or too long.")
    raw = value.strip()
    if not raw or any(ord(char) < 0x20 or char.isspace() for char in raw):
        raise UnsafePublicURL("The website URL contains whitespace or control characters.")
    if raw.startswith("//"):
        raise UnsafePublicURL("A website URL must include a host.")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", raw, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:", raw, re.I):
            raise UnsafePublicURL("Only HTTP and HTTPS websites are supported.")
        raw = "https://" + raw
    try:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.casefold()
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise UnsafePublicURL("The website URL is malformed.") from exc
    if scheme not in {"http", "https"}:
        raise UnsafePublicURL("Only HTTP and HTTPS websites are supported.")
    if not host or parsed.username is not None or parsed.password is not None:
        raise UnsafePublicURL("A public website host without embedded credentials is required.")
    if port is not None and port not in {80, 443}:
        raise UnsafePublicURL("Only standard public HTTP and HTTPS ports are supported.")
    if port == 80 and scheme != "http" or port == 443 and scheme != "https":
        raise UnsafePublicURL("The URL port does not match its HTTP scheme.")

    host = host.rstrip(".").casefold()
    if not host or "%" in host or host == "localhost" or host.endswith(_LOCAL_SUFFIXES):
        raise UnsafePublicURL("Local and internal website destinations are blocked.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if _NUMERIC_HOST.fullmatch(host):
            raise UnsafePublicURL("The numeric IP address is malformed.")
        try:
            host = host.encode("idna").decode("ascii").casefold()
        except UnicodeError as exc:
            raise UnsafePublicURL("The website host is malformed.") from exc
        if "." not in host or len(host) > 253 or any(not _LABEL.fullmatch(label) for label in host.split(".")):
            raise UnsafePublicURL("A complete public website domain is required.")
        address = None
    if address is not None and not address.is_global:
        raise UnsafePublicURL("Private and reserved IP destinations are blocked.")

    for field in (parsed.query, parsed.fragment):
        try:
            keys = [key for key, _ in parse_qsl(field, keep_blank_values=True)]
        except ValueError as exc:
            raise UnsafePublicURL("The website URL parameters are malformed.") from exc
        if any(_SENSITIVE_QUERY_KEY.search(key) for key in keys):
            raise UnsafePublicURL("Credential-bearing URL parameters are not allowed.")

    if resolve_dns and address is None:
        try:
            answers = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise UnsafePublicURL("The public website host could not be resolved.") from exc
        resolved = set()
        for answer in answers:
            try:
                resolved.add(ipaddress.ip_address(answer[4][0].split("%", 1)[0]))
            except ValueError as exc:
                raise UnsafePublicURL("The public website host resolved to an invalid address.") from exc
        if not resolved or any(not item.is_global for item in resolved):
            raise UnsafePublicURL("The website host resolves to a private or reserved network.")

    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host
    if port is not None and port not in {80, 443}:
        netloc = f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, parsed.path or "/", parsed.query, parsed.fragment))


def verify_public_redirect(requested: str, observed: str) -> str:
    """Validate the browser's final destination and refuse scheme downgrade.

    Public redirects are reported to the user as the verified final URL;
    nonpublic, malformed, and HTTPS-to-HTTP redirects are rejected.
    """
    start = urlsplit(normalize_public_http_url(requested))
    final = normalize_public_http_url(observed)
    destination = urlsplit(final)
    if start.scheme == "https" and destination.scheme != "https":
        raise UnsafePublicURL("The browser redirected from HTTPS to an insecure HTTP page.")
    if start.hostname != destination.hostname:
        raise UnsafePublicURL("The browser redirected away from the exact approved public host.")
    final = normalize_public_http_url(final, resolve_dns=True)
    return final
