"""Credential-gated Google and Twilio adapters. No network calls happen at import time."""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken

from backend.app.config import Settings, get_settings, is_placeholder_secret
from backend.app.db.models import AssistantAccount

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GMAIL_SCOPES = (
    "openid", "email", "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
)
CALENDAR_SCOPES = ("openid", "email", "https://www.googleapis.com/auth/calendar.events.owned")
_SAFE_TWILIO_STATUS = {"queued", "initiated", "ringing", "in-progress", "completed", "busy", "failed", "no-answer", "canceled"}


class ProviderUnavailable(RuntimeError):
    pass


class ProviderFailure(RuntimeError):
    def __init__(self, code: str, retryable: bool = False):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


def _fernet(settings: Settings | None = None) -> Fernet:
    key = (settings or get_settings()).assistant_token_encryption_key.strip()
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ProviderUnavailable("Provider token encryption is not configured") from exc


def encrypt_token(value: str, settings: Settings | None = None) -> str:
    return _fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_token(value: str, settings: Settings | None = None) -> str:
    try:
        return _fernet(settings).decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError) as exc:
        raise ProviderUnavailable("Stored provider credentials cannot be decrypted; reconnect the account") from exc


def google_ready(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    try:
        _fernet(cfg)
        encryption_ready = True
    except ProviderUnavailable:
        encryption_ready = False
    return bool(encryption_ready and cfg.app_env == "production" and cfg.assistant_live_operations_enabled and cfg.assistant_google_live_enabled
                and cfg.google_oauth_client_id and cfg.google_oauth_client_secret
                and cfg.google_oauth_redirect_uri and not is_placeholder_secret(cfg.google_oauth_client_id)
                and not is_placeholder_secret(cfg.google_oauth_client_secret))


def google_scopes(provider: str) -> tuple[str, ...]:
    if provider == "gmail": return GMAIL_SCOPES
    if provider == "calendar": return CALENDAR_SCOPES
    raise ProviderUnavailable("Unsupported Google provider")


def google_authorization_url(provider: str, state: str, challenge: str, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    if not google_ready(cfg):
        raise ProviderUnavailable("Google OAuth is not configured or enabled")
    return GOOGLE_AUTH_URL + "?" + urlencode({
        "client_id": cfg.google_oauth_client_id,
        "redirect_uri": cfg.google_oauth_redirect_uri,
        "response_type": "code", "scope": " ".join(google_scopes(provider)),
        "access_type": "offline", "include_granted_scopes": "true",
        "prompt": "consent", "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def google_exchange_code(code: str, verifier: str, settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if not google_ready(cfg): raise ProviderUnavailable("Google OAuth is not configured or enabled")
    try:
        response = httpx.post(GOOGLE_TOKEN_URL, data={
            "code": code, "client_id": cfg.google_oauth_client_id, "client_secret": cfg.google_oauth_client_secret,
            "redirect_uri": cfg.google_oauth_redirect_uri, "grant_type": "authorization_code", "code_verifier": verifier,
        }, timeout=15)
        if response.status_code >= 400: raise ProviderFailure("oauth_exchange_rejected", response.status_code >= 500)
        payload = response.json()
    except httpx.HTTPError as exc: raise ProviderFailure("oauth_exchange_unavailable", True) from exc
    if not isinstance(payload, dict) or not payload.get("access_token") or not payload.get("expires_in"):
        raise ProviderFailure("oauth_exchange_invalid_response")
    return payload


def google_refresh_token(refresh_token: str, settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if not google_ready(cfg): raise ProviderUnavailable("Google OAuth is not configured or enabled")
    try:
        response = httpx.post(GOOGLE_TOKEN_URL, data={
            "client_id": cfg.google_oauth_client_id, "client_secret": cfg.google_oauth_client_secret,
            "refresh_token": refresh_token, "grant_type": "refresh_token",
        }, timeout=15)
        if response.status_code >= 400: raise ProviderFailure("oauth_refresh_rejected", response.status_code in (429, 500, 502, 503, 504))
        payload = response.json()
    except httpx.HTTPError as exc: raise ProviderFailure("oauth_refresh_unavailable", True) from exc
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise ProviderFailure("oauth_refresh_invalid_response")
    return payload


def google_revoke_token(token: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not google_ready(cfg): return
    try:
        response = httpx.post(GOOGLE_REVOKE_URL, data={"token": token}, timeout=10)
        if response.status_code >= 500: raise ProviderFailure("oauth_revoke_unavailable", True)
    except httpx.HTTPError as exc: raise ProviderFailure("oauth_revoke_unavailable", True) from exc


def google_request(account: AssistantAccount, method: str, path: str, *, params=None, json_body=None,
                   settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if not account.access_token_enc: raise ProviderUnavailable("Google account is disconnected")
    token = decrypt_token(account.access_token_enc, cfg)
    if account.token_expires_at and account.token_expires_at <= datetime.now(timezone.utc) + timedelta(seconds=45):
        if not account.refresh_token_enc: raise ProviderUnavailable("Google authorization expired; reconnect the account")
        refreshed = google_refresh_token(decrypt_token(account.refresh_token_enc, cfg), cfg)
        account.access_token_enc = encrypt_token(refreshed["access_token"], cfg)
        account.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
        token = refreshed["access_token"]
    base = GMAIL_API if account.provider == "gmail" else CALENDAR_API
    try:
        response = httpx.request(method, base + path, params=params, json=json_body,
                                 headers={"Authorization": "Bearer " + token}, timeout=20)
        if response.status_code == 401: raise ProviderFailure("google_reauthorization_required")
        if response.status_code == 429 or response.status_code >= 500: raise ProviderFailure("google_api_temporary_failure", True)
        if response.status_code >= 400: raise ProviderFailure("google_api_request_rejected")
        data = response.json() if response.content else {}
    except httpx.HTTPError as exc: raise ProviderFailure("google_api_unavailable", True) from exc
    if not isinstance(data, dict): raise ProviderFailure("google_api_invalid_response")
    return data


def message_classification(sender: str, subject: str, snippet: str) -> tuple[str, bool]:
    """Conservative deterministic triage; email text is never interpreted as instructions."""
    combined = f"{sender} {subject} {snippet}".casefold()
    automated = any(x in sender.casefold() for x in ("no-reply", "noreply", "mailer-daemon", "newsletter"))
    if any(x in combined for x in ("password reset", "security code", "verify your account", "wire transfer", "invoice payment")):
        return "security_or_financial", False
    if any(x in combined for x in ("assignment", "exam", "submission", "due date", "deadline", "homework")):
        return "deadline_or_school", not automated
    if any(x in combined for x in ("unsubscribe", "newsletter", "weekly digest")) or automated:
        return "bulk_or_automated", False
    return "other", False


_EXPLICIT_DATE = re.compile(r"\b(?:due|deadline|submit|by)\s+(?:on\s+)?([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2})\b", re.I)


def extract_explicit_date_phrases(subject: str, snippet: str) -> list[tuple[str, str]]:
    """Find explicit date phrases only; never infer a date/time or confirm a deadline."""
    text = (subject[:500] + "\n" + snippet[:1200])
    return [(match.group(0)[:160], match.group(1)[:100]) for match in _EXPLICIT_DATE.finditer(text)]


def twilio_live_ready(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    prefixes = [item.strip() for item in cfg.twilio_allowed_destination_prefixes.split(",") if item.strip()]
    allowlist_valid = bool(prefixes) and all(re.fullmatch(r"\+[1-9]\d{0,3}", item) for item in prefixes)
    return bool(cfg.app_env == "production" and cfg.assistant_live_operations_enabled and cfg.twilio_live_calls_enabled
                and cfg.twilio_account_sid and cfg.twilio_auth_token
                and cfg.twilio_from_number and cfg.twilio_status_callback_url and allowlist_valid)


def twilio_destination_allowed(phone: str, settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    prefixes = [item.strip() for item in cfg.twilio_allowed_destination_prefixes.split(",") if item.strip()]
    if not prefixes or not all(re.fullmatch(r"\+[1-9]\d{0,3}", item) for item in prefixes):
        return False
    return any(phone.startswith(prefix) for prefix in prefixes)


def _twiml(text: str, language: str) -> str:
    escaped = html.escape(text[:1200])
    if language == "te":
        return f'<Response><Say language="te-IN" voice="Google.te-IN-Standard-A">{escaped}</Say></Response>'
    if language == "mixed":
        return (f'<Response><Say language="en-US" voice="Polly.Joanna">{escaped}</Say>'
                '<Say language="te-IN" voice="Google.te-IN-Standard-A">మీ గడువు దగ్గరలో ఉంది. దయచేసి సమయానికి పూర్తి చేయండి.</Say></Response>')
    return f'<Response><Say language="en-US" voice="Polly.Joanna">{escaped}</Say></Response>'


def twilio_create_call(to_number: str, text: str, language: str, settings: Settings | None = None) -> dict:
    cfg = settings or get_settings()
    if not twilio_live_ready(cfg): raise ProviderUnavailable("Live telephony is disabled or not configured")
    try:
        response = httpx.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{cfg.twilio_account_sid}/Calls.json",
            data={"To": to_number, "From": cfg.twilio_from_number, "Twiml": _twiml(text, language),
                  "StatusCallback": cfg.twilio_status_callback_url,
                  "StatusCallbackMethod": "POST",
                  "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"]},
            auth=(cfg.twilio_account_sid, cfg.twilio_auth_token), timeout=20,
        )
        if response.status_code == 429: raise ProviderFailure("telephony_rate_limited", True)
        if response.status_code >= 500: raise ProviderFailure("telephony_outcome_uncertain", False)
        if response.status_code >= 400: raise ProviderFailure("telephony_request_rejected")
        result = response.json()
    except httpx.HTTPError as exc: raise ProviderFailure("telephony_outcome_uncertain", False) from exc
    if not isinstance(result, dict) or not result.get("sid") or result.get("status") not in _SAFE_TWILIO_STATUS:
        raise ProviderFailure("telephony_invalid_response")
    return {"sid": result["sid"], "status": result["status"]}


def verify_twilio_signature(url: str, params: dict[str, list[str]], signature: str, auth_token: str) -> bool:
    if not signature or not auth_token: return False
    payload = url
    for key in sorted(params):
        for value in sorted(params[key]):
            payload += key + value
    digest = hmac.new(auth_token.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1).digest()
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


def twilio_verify_start(phone: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    if not (cfg.app_env == "production" and cfg.assistant_live_operations_enabled and cfg.twilio_live_calls_enabled and cfg.twilio_account_sid and cfg.twilio_auth_token and cfg.twilio_verify_service_sid):
        raise ProviderUnavailable("Phone verification provider is not configured")
    try:
        response = httpx.post(f"https://verify.twilio.com/v2/Services/{cfg.twilio_verify_service_sid}/Verifications",
                              data={"To": phone, "Channel": "sms"}, auth=(cfg.twilio_account_sid, cfg.twilio_auth_token), timeout=15)
        if response.status_code >= 400: raise ProviderFailure("phone_verification_start_failed", response.status_code >= 500)
    except httpx.HTTPError as exc: raise ProviderFailure("phone_verification_unavailable", True) from exc

def twilio_verify_check(phone: str, code: str, settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    if not (cfg.app_env == "production" and cfg.assistant_live_operations_enabled and cfg.twilio_live_calls_enabled and cfg.twilio_account_sid and cfg.twilio_auth_token and cfg.twilio_verify_service_sid):
        raise ProviderUnavailable("Phone verification provider is not configured")
    try:
        response = httpx.post(f"https://verify.twilio.com/v2/Services/{cfg.twilio_verify_service_sid}/VerificationCheck",
                              data={"To": phone, "Code": code}, auth=(cfg.twilio_account_sid, cfg.twilio_auth_token), timeout=15)
        if response.status_code >= 400: raise ProviderFailure("phone_verification_rejected")
        return response.json().get("status") == "approved"
    except httpx.HTTPError as exc: raise ProviderFailure("phone_verification_unavailable", True) from exc

\n