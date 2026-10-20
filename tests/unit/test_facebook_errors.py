from app.connectors.facebook.errors import map_facebook_error


def test_invalid_token_maps_to_invalid_token():
    assert map_facebook_error(190, 463) == "invalid_token"


def test_rate_limit_codes_map_to_rate_limited():
    for code in (4, 17, 32, 613):
        assert map_facebook_error(code, None) == "rate_limited"


def test_temporary_codes_map_to_temporary_unavailable():
    assert map_facebook_error(2, None) == "temporary_unavailable"


def test_invalid_parameter_maps_to_invalid_request():
    assert map_facebook_error(100, None) == "invalid_request"


def test_permission_range_maps_to_permission_denied():
    assert map_facebook_error(200, None) == "permission_denied"


def test_unmapped_code_falls_back_to_unknown_error():
    assert map_facebook_error(9999, None) == "unknown_error"
    assert map_facebook_error(None, None) == "unknown_error"
