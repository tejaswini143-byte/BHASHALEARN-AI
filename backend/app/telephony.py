"""Guarded LiveKit SIP dispatch. No call is possible without affirmative student consent."""
from .settings import settings


def telephony_blockers(preferences, verified_test_numbers: set[str] | None = None) -> list[str]:
    missing = []
    if not settings.livekit_url or not settings.livekit_api_key or not settings.livekit_api_secret:
        missing.append("LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET")
    if not settings.sip_outbound_trunk_id:
        missing.append("SIP_OUTBOUND_TRUNK_ID")
    if not settings.sip_caller_id:
        missing.append("SIP_CALLER_ID (approved caller identity)")
    if not preferences or not preferences.call_enabled or not preferences.call_consent_at or preferences.opted_out_at:
        missing.append("active student call consent")
    if not preferences or not preferences.phone_e164 or not preferences.phone_verified_at:
        missing.append("verified student phone number")
    if not settings.allow_test_calls:
        missing.append("ALLOW_TEST_CALLS=true")
    if verified_test_numbers is not None and preferences and preferences.phone_e164 not in verified_test_numbers:
        missing.append("phone number allowlisted as a verified test number")
    return missing

