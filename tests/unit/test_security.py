import time

from app.core.security import (
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)


def test_hash_password_round_trip():
    password_hash = hash_password("s3cret!")

    assert verify_password("s3cret!", password_hash) is True
    assert verify_password("wrong", password_hash) is False


def test_session_token_round_trip():
    token = create_session_token("user-123")

    assert read_session_token(token) == "user-123"


def test_session_token_rejects_tampered_value():
    token = create_session_token("user-123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    assert read_session_token(tampered) is None


def test_session_token_rejects_expired_value(monkeypatch):
    import app.core.security as security_module

    monkeypatch.setattr(security_module, "SESSION_MAX_AGE_SECONDS", 1)
    token = security_module.create_session_token("user-123")
    time.sleep(2.1)

    assert security_module.read_session_token(token) is None
