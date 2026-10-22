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


OAUTH_STATE_MINUTES = 10


def create_oauth_state(user_id: int, source_id: int) -> str:
    """Signed, short-lived `state` for an OAuth redirect: who started it and for which source."""
    now = datetime.now(UTC)
    payload = {
        "purpose": "oauth_state",
        "sub": str(user_id),
        "source_id": source_id,
        "iat": now,
        "exp": now + timedelta(minutes=OAUTH_STATE_MINUTES),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_oauth_state(state: str) -> tuple[int, int]:
    """(user_id, source_id) from an OAuth state, or raise InvalidTokenError."""
    try:
        payload = jwt.decode(state, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp"]})
        if payload.get("purpose") != "oauth_state":
            raise InvalidTokenError("not an OAuth state")
        return int(payload["sub"]), int(payload["source_id"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as exc:
        raise InvalidTokenError(str(exc)) from exc


def decode_access_token(token: str) -> int:
    """Return the user id stored in the token, or raise InvalidTokenError."""
    try:
        payload = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp"]}
        )
        if "purpose" in payload:  # e.g. an OAuth state is not a login token
            raise InvalidTokenError("not an access token")
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
