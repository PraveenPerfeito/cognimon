from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

from app.core.errors import AuthenticationError

password_hash = PasswordHash.recommended()


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: str
    email: str
    role: str
    token_id: str
    issued_at: int
    expires_at: int
    token_use: str


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


def _create_token(
    *,
    subject: str,
    email: str,
    role: str,
    secret: str,
    algorithm: str,
    expires_delta: timedelta,
    token_use: str,
) -> str:
    issued_at = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "email": email,
        "role": role,
        "jti": str(uuid4()),
        "token_use": token_use,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + expires_delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_access_token(
    *,
    subject: str,
    email: str,
    role: str,
    secret: str,
    algorithm: str,
    expires_in_minutes: int,
) -> str:
    return _create_token(
        subject=subject,
        email=email,
        role=role,
        secret=secret,
        algorithm=algorithm,
        expires_delta=timedelta(minutes=expires_in_minutes),
        token_use="access",
    )


def create_refresh_token(
    *,
    subject: str,
    email: str,
    role: str,
    secret: str,
    algorithm: str,
    expires_in_days: int,
) -> str:
    return _create_token(
        subject=subject,
        email=email,
        role=role,
        secret=secret,
        algorithm=algorithm,
        expires_delta=timedelta(days=expires_in_days),
        token_use="refresh",
    )


def extract_bearer_token(*, authorization_header: str | None, scheme: str) -> str | None:
    if not authorization_header:
        return None

    parts = authorization_header.strip().split()
    if len(parts) != 2 or parts[0].lower() != scheme.lower():
        raise AuthenticationError("Invalid bearer token format.")
    return parts[1]


def _decode_token(
    *,
    token: str,
    secret: str,
    algorithm: str,
    expected_token_use: str,
    invalid_token_message: str,
) -> TokenClaims:
    try:
        payload: dict[str, Any] = jwt.decode(token, secret, algorithms=[algorithm])
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(invalid_token_message) from exc

    subject = payload.get("sub")
    email = payload.get("email")
    role = payload.get("role")
    token_id = payload.get("jti")
    token_use = payload.get("token_use")
    issued_at = payload.get("iat")
    expires_at = payload.get("exp")
    if not all([subject, email, role, token_id, token_use, issued_at, expires_at]):
        raise AuthenticationError("Malformed token payload.")
    if token_use != expected_token_use:
        raise AuthenticationError(invalid_token_message)

    return TokenClaims(
        subject=subject,
        email=email,
        role=role,
        token_id=token_id,
        issued_at=int(issued_at),
        expires_at=int(expires_at),
        token_use=token_use,
    )


def decode_access_token(*, token: str, secret: str, algorithm: str) -> TokenClaims:
    return _decode_token(
        token=token,
        secret=secret,
        algorithm=algorithm,
        expected_token_use="access",
        invalid_token_message="Invalid or expired access token.",
    )


def decode_refresh_token(*, token: str, secret: str, algorithm: str) -> TokenClaims:
    return _decode_token(
        token=token,
        secret=secret,
        algorithm=algorithm,
        expected_token_use="refresh",
        invalid_token_message="Invalid or expired refresh token.",
    )

