"""Encryption of connector credentials stored in the database (e.g. the Gmail refresh token).

Uses Fernet (AES + HMAC) with the key from TOKEN_ENCRYPTION_KEY. The decrypted value is only
used inside the backend to call the external API; it is never returned by an endpoint.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionKeyError(RuntimeError):
    """TOKEN_ENCRYPTION_KEY is missing or is not a valid Fernet key."""


class DecryptionError(RuntimeError):
    """The stored value was encrypted with another key or was changed."""


def encryption_configured() -> bool:
    try:
        _fernet()
    except EncryptionKeyError:
        return False
    return True


def _fernet() -> Fernet:
    key = (settings.token_encryption_key or "").strip()
    if not key:
        raise EncryptionKeyError("TOKEN_ENCRYPTION_KEY is not set. Add it to backend/.env (see .env.example).")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise EncryptionKeyError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key (see .env.example).") from None


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise DecryptionError("Stored credentials could not be decrypted. Connect the account again.") from None
