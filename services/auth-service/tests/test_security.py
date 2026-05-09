from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.core.security import hash_password, verify_and_rehash_password


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
