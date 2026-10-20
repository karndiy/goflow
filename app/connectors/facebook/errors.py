RATE_LIMIT_CODES = {4, 17, 32, 613}
TEMPORARY_CODES = {1, 2}
INVALID_TOKEN_CODE = 190
INVALID_PARAMETER_CODE = 100


def map_facebook_error(code: int | None, subcode: int | None) -> str:
    if code == INVALID_TOKEN_CODE:
        return "invalid_token"
    if code in RATE_LIMIT_CODES:
        return "rate_limited"
    if code in TEMPORARY_CODES:
        return "temporary_unavailable"
    if code == INVALID_PARAMETER_CODE:
        return "invalid_request"
    if code is not None and 200 <= code < 300:
        return "permission_denied"
    return "unknown_error"
