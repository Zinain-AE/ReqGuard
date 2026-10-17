"""Password hashing (Argon2id) and JWT access tokens (HS256)."""

from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

ALGORITHM = "HS256"

_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """The token is missing, malformed, expired or signed with another secret."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _secret() -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set. Add it to backend/.env (see .env.example).")
    return settings.jwt_secret


def create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id stored in the token, or raise InvalidTokenError."""
    try:
        payload = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
