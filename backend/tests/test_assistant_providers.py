"""Provider adapter safety contracts; these tests make no network requests."""
import base64
import hashlib
import hmac
from types import SimpleNamespace

from cryptography.fernet import Fernet

from backend.app.services.assistant_providers import (
    ProviderUnavailable,
    decrypt_token,
    encrypt_token,
    google_ready,
    google_scopes,
    message_classification,
    verify_twilio_signature,
    twilio_destination_allowed,
    twilio_live_ready,
    _twiml,
)


def provider_settings(**overrides):
    values = {
        "app_env": "development", "assistant_live_operations_enabled": False,
        "assistant_google_live_enabled": False, "google_oauth_client_id": "",
        "google_oauth_client_secret": "", "google_oauth_redirect_uri": "",
        "assistant_token_encryption_key": "", "twilio_live_calls_enabled": False,
        "twilio_account_sid": "", "twilio_auth_token": "", "twilio_from_number": "",
        "twilio_status_callback_url": "", "twilio_allowed_destination_prefixes": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_provider_credentials_are_encrypted_and_key_is_required():
    key = Fernet.generate_key().decode()
    config = provider_settings(assistant_token_encryption_key=key)
    token = encrypt_token("fake-access-token", config)
    assert token != "fake-access-token"
    assert decrypt_token(token, config) == "fake-access-token"
    try:
        decrypt_token(token, provider_settings(assistant_token_encryption_key=Fernet.generate_key().decode()))
    except ProviderUnavailable:
        pass
    else:
        raise AssertionError("A token encrypted with another key must not decrypt")


def test_live_google_requires_all_explicit_switches_and_encryption_key():
    base = dict(app_env="production", assistant_live_operations_enabled=True,
        assistant_google_live_enabled=True, google_oauth_client_id="fake-client-id.apps.googleusercontent.com",
        google_oauth_client_secret="fake-secret", google_oauth_redirect_uri="https://example.invalid/callback",
        assistant_token_encryption_key=Fernet.generate_key().decode())
    assert google_ready(provider_settings(**base))
    assert not google_ready(provider_settings(**{**base, "assistant_live_operations_enabled": False}))
    assert not google_ready(provider_settings(**{**base, "assistant_token_encryption_key": ""}))


def test_google_scopes_are_separated_and_minimal():
    gmail = set(google_scopes("gmail"))
    calendar = set(google_scopes("calendar"))
    assert "https://www.googleapis.com/auth/gmail.readonly" in gmail
    assert "https://www.googleapis.com/auth/gmail.send" in gmail
    assert "https://www.googleapis.com/auth/calendar.events.owned" in calendar
    assert not any("gmail" in scope for scope in calendar)


def test_mail_classification_avoids_automated_and_security_replies():
    assert message_classification("no-reply@school.example", "Assignment due date", "Submit by Friday") == ("deadline_or_school", False)
    assert message_classification("person@example.com", "Password reset", "security code") == ("security_or_financial", False)


def test_twilio_signature_checks_exact_signed_parameters():
    url = "https://assistant.example/api/v1/assistant/webhooks/twilio/status"
    params = {"CallSid": ["CA123"], "CallStatus": ["completed"]}
    token = "fake-test-token"
    raw = url + "CallSidCA123" + "CallStatuscompleted"
    signature = base64.b64encode(hmac.new(token.encode(), raw.encode(), hashlib.sha1).digest()).decode()
    assert verify_twilio_signature(url, params, signature, token)
    assert not verify_twilio_signature(url + "?x=1", params, signature, token)


def test_twiml_escapes_untrusted_deadline_text():
    xml = _twiml("<deadline> & verify", "te")
    assert "&lt;deadline&gt; &amp; verify" in xml
    assert "<deadline>" not in xml
    assert "language=\"te-IN\"" in xml


def test_live_twilio_requires_valid_explicit_destination_allowlist():
    base = dict(app_env="production", assistant_live_operations_enabled=True, twilio_live_calls_enabled=True,
        twilio_account_sid="ACfake", twilio_auth_token="fake", twilio_from_number="+15557654321",
        twilio_status_callback_url="https://example.invalid/callback")
    assert not twilio_live_ready(provider_settings(**base))
    approved = provider_settings(**{**base, "twilio_allowed_destination_prefixes": "+1,+44"})
    assert twilio_live_ready(approved)
    assert twilio_destination_allowed("+15551234567", approved)
    assert twilio_destination_allowed("+447700900123", approved)
    assert not twilio_destination_allowed("+919876543210", approved)
    assert not twilio_destination_allowed("+15551234567", provider_settings(**{**base, "twilio_allowed_destination_prefixes": "+1,invalid"}))
