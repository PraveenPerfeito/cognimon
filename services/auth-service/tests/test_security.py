import pytest
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_and_rehash_password,
)


def test_password_hash_uses_configured_pepper() -> None:
    hashed_password = hash_password("StrongPass123", pepper="cognimon-pepper")

    is_valid, upgraded_hash = verify_and_rehash_password(
        "StrongPass123",
        hashed_password,
        pepper="cognimon-pepper",
    )

    assert is_valid is True
    assert upgraded_hash is None


def test_password_verify_rehashes_legacy_hash() -> None:
    legacy_hasher = PasswordHash(
        (
            Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1),
        )
    )
    legacy_hash = legacy_hasher.hash("StrongPass123legacy-pepper")

    is_valid, upgraded_hash = verify_and_rehash_password(
        "StrongPass123",
        legacy_hash,
        pepper="legacy-pepper",
    )

    assert is_valid is True
    assert upgraded_hash is not None
    assert upgraded_hash != legacy_hash


def test_password_verify_supports_transition_from_unpeppered_hash() -> None:
    legacy_hash = hash_password("StrongPass123", pepper="")

    is_valid, upgraded_hash = verify_and_rehash_password(
        "StrongPass123",
        legacy_hash,
        pepper="new-pepper",
    )

    assert is_valid is True
    assert upgraded_hash is not None
    assert upgraded_hash != legacy_hash


def test_refresh_token_decode_rejects_access_token() -> None:
    token_secret = "test-secret-key-with-32-characters"
    access_token = create_access_token(
        subject="user-123",
        email="learner@cognimon.dev",
        role="learner",
        secret=token_secret,
        algorithm="HS256",
        expires_in_minutes=60,
    )

    with pytest.raises(AuthenticationError, match="Invalid or expired refresh token."):
        decode_refresh_token(
            token=access_token,
            secret=token_secret,
            algorithm="HS256",
        )


def test_access_token_decode_rejects_refresh_token() -> None:
    token_secret = "test-secret-key-with-32-characters"
    refresh_token = create_refresh_token(
        subject="user-123",
        email="learner@cognimon.dev",
        role="learner",
        secret=token_secret,
        algorithm="HS256",
        expires_in_days=14,
    )

    with pytest.raises(AuthenticationError, match="Invalid or expired access token."):
        decode_access_token(
            token=refresh_token,
            secret=token_secret,
            algorithm="HS256",
        )
