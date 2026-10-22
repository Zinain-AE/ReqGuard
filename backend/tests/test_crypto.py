"""Encryption of stored connector credentials."""

import pytest
from cryptography.fernet import Fernet

from app.core import crypto
from app.core.config import settings


def test_round_trip(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    token = crypto.encrypt("1//refresh-token-value")
    assert "refresh-token-value" not in token
    assert crypto.decrypt(token) == "1//refresh-token-value"


def test_missing_or_invalid_key(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", None)
    assert not crypto.encryption_configured()
    with pytest.raises(crypto.EncryptionKeyError, match="TOKEN_ENCRYPTION_KEY is not set"):
        crypto.encrypt("x")

    monkeypatch.setattr(settings, "token_encryption_key", "not-a-key")
    assert not crypto.encryption_configured()
    with pytest.raises(crypto.EncryptionKeyError, match="not a valid Fernet key"):
        crypto.encrypt("x")


def test_value_from_other_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    token = crypto.encrypt("secret")
    monkeypatch.setattr(settings, "token_encryption_key", Fernet.generate_key().decode())
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(token)
