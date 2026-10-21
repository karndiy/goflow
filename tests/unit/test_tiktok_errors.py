from app.connectors.tiktok.errors import map_tiktok_error


def test_token_related_codes_map_to_invalid_token():
    assert map_tiktok_error("access_token_invalid") == "invalid_token"
    assert map_tiktok_error("token_expired") == "invalid_token"


def test_rate_limit_codes_map_to_rate_limited():
    assert map_tiktok_error("rate_limit_exceeded") == "rate_limited"
    assert map_tiktok_error("spam_risk_too_many_posts") == "rate_limited"


def test_transient_codes_map_to_temporary_unavailable():
    assert map_tiktok_error("internal_error") == "temporary_unavailable"
    assert map_tiktok_error("server_error_timeout") == "temporary_unavailable"


def test_permission_codes_map_to_permission_denied():
    assert map_tiktok_error("scope_not_authorized") == "permission_denied"
    assert map_tiktok_error("user_banned_from_posting") == "permission_denied"


def test_unmapped_code_falls_back_to_invalid_request():
    assert map_tiktok_error("picture_size_check_failed") == "invalid_request"
    assert map_tiktok_error("file_format_check_failed") == "invalid_request"


def test_ok_or_missing_code_maps_to_unknown_error():
    assert map_tiktok_error("ok") == "unknown_error"
    assert map_tiktok_error(None) == "unknown_error"
