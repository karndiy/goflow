"""Maps TikTok's error codes (Content Posting API `error.code`, and status-fetch `fail_reason`)
onto GoFlow's shared retry/reauth vocabulary (app/connectors/errors.py).

TikTok doesn't publish one fixed enum of every possible code in the parts of the docs available
at implementation time, so this matches by substring rather than an exact lookup table. That's
deliberately conservative: unrecognized codes fall back to "invalid_request" (not retried) rather
than being guessed as transient, per Claude.md's "retry only errors that are safe and eligible."
Revisit against real sandbox error responses before relying on this for anything high-stakes.
"""

REAUTH_SUBSTRINGS = ("token_invalid", "token_expired", "access_token", "invalid_client")
RETRYABLE_RATE_SUBSTRINGS = ("rate_limit", "too_many", "spam_risk")
RETRYABLE_TRANSIENT_SUBSTRINGS = ("server_error", "internal_error", "timeout", "unavailable")
PERMISSION_SUBSTRINGS = ("scope_not_authorized", "not_authorized", "banned", "permission")


def map_tiktok_error(code: str | None) -> str:
    if not code or code == "ok":
        return "unknown_error"
    lowered = code.lower()
    if any(s in lowered for s in REAUTH_SUBSTRINGS):
        return "invalid_token"
    if any(s in lowered for s in RETRYABLE_RATE_SUBSTRINGS):
        return "rate_limited"
    if any(s in lowered for s in RETRYABLE_TRANSIENT_SUBSTRINGS):
        return "temporary_unavailable"
    if any(s in lowered for s in PERMISSION_SUBSTRINGS):
        return "permission_denied"
    return "invalid_request"
