from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.errors import AuthenticationError

password_hash = PasswordHash.recommended()


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    subject: str
    email: str
    role: str
    issued_at: int
    expires_at: int


def _apply_password_pepper(password: str, pepper: str) -> str:
    return f"{password}{pepper}" if pepper else password


def hash_password(password: str, *, pepper: str = "") -> str:
    return password_hash.hash(_apply_password_pepper(password, pepper))


def verify_password(password: str, hashed_password: str, *, pepper: str = "") -> bool:
    return password_hash.verify(_apply_password_pepper(password, pepper), hashed_password)


def verify_and_rehash_password(
    password: str,
    hashed_password: str,
    *,
    pepper: str = "",
) -> tuple[bool, str | None]:
    peppered_password = _apply_password_pepper(password, pepper)
    password_is_valid, upgraded_hash = password_hash.verify_and_update(
        peppered_password,
        hashed_password,
    )
    if password_is_valid:
        return password_is_valid, upgraded_hash

    if not pepper:
        return False, None

    legacy_password_is_valid, _ = password_hash.verify_and_update(password, hashed_password)
    if not legacy_password_is_valid:
        return False, None

    return True, hash_password(password, pepper=pepper)


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    secret: str,
    algorithm: str,
    expires_in_minutes: int,
) -> str:
    issued_at = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(minutes=expires_in_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def extract_bearer_token(*, authorization_header: str | None, scheme: str) -> str | None:
    if not authorization_header:
        return None

    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != scheme.lower():
        raise AuthenticationError("Invalid bearer token format.")
    return parts[1]


def decode_access_token(*, token: str, secret: str, algorithm: str) -> AccessTokenClaims:
    try:
        payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid or expired access token.") from exc

    subject = payload.get("sub")
    email = payload.get("email")
    role = payload.get("role")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    if not all([subject, email, role, issued_at, expires_at]):
        raise AuthenticationError("Malformed token payload.")

    return AccessTokenClaims(
        subject=subject,
        email=email,
        role=role,
        issued_at=int(issued_at),
        expires_at=int(expires_at),
    )

