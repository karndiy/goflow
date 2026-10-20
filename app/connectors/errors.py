"""Error codes connectors map provider errors onto; drives the worker's retry classification."""

RETRYABLE_ERROR_CODES = {"rate_limited", "temporary_unavailable"}
REAUTH_ERROR_CODES = {"invalid_token"}
