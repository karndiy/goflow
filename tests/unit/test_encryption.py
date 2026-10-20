import pytest

from app.core.encryption import decrypt_token, encrypt_token


def test_encrypt_decrypt_round_trip():
    ciphertext = encrypt_token("super-secret-access-token")

    assert ciphertext != "super-secret-access-token"
    assert decrypt_token(ciphertext) == "super-secret-access-token"


def test_decrypt_rejects_tampered_ciphertext():
    ciphertext = encrypt_token("super-secret-access-token")
    tampered = ciphertext[:-1] + ("a" if ciphertext[-1] != "a" else "b")

    with pytest.raises(ValueError):
        decrypt_token(tampered)


def test_encrypt_raises_when_key_not_configured(monkeypatch):
    import app.core.encryption as encryption_module

    monkeypatch.setattr(encryption_module.settings, "token_encryption_key", "")

    with pytest.raises(RuntimeError):
        encryption_module.encrypt_token("anything")
