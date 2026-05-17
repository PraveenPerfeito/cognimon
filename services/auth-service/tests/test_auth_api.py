from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_password,
)
from app.db.models import PasswordResetToken, User, UserRole


@pytest.mark.asyncio
async def test_register_login_and_fetch_profile(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "learner@cognimon.dev",
            "display_name": "Learner One",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["role"] == "learner"

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "learner@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]
    assert login_response.json()["refresh_expires_in"] > login_response.json()["expires_in"]

    profile_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "learner@cognimon.dev"

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]
    assert refresh_response.json()["refresh_token"]


@pytest.mark.asyncio
async def test_registration_and_login_emit_audit_logs(client, caplog):
    caplog.set_level("INFO", logger="app.audit")

    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit@cognimon.dev",
            "display_name": "Audit User",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "audit@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    assert login_response.status_code == 200

    audit_messages = [record.message for record in caplog.records if record.name == "app.audit"]
    assert any("audit_event=auth.register_success" in message for message in audit_messages)
    assert any("audit_event=auth.login_success" in message for message in audit_messages)


@pytest.mark.asyncio
async def test_failed_login_emits_audit_log(client, caplog):
    caplog.set_level("INFO", logger="app.audit")

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "missing-user@cognimon.dev",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 401
    audit_messages = [record.message for record in caplog.records if record.name == "app.audit"]
    assert any(
        "audit_event=auth.login_failed" in message and "reason=user_not_found" in message
        for message in audit_messages
    )


@pytest.mark.asyncio
async def test_duplicate_registration_emits_audit_log(client, caplog):
    caplog.set_level("INFO", logger="app.audit")

    payload = {
        "email": "audit-duplicate@cognimon.dev",
        "display_name": "Duplicate User",
        "password": "StrongPass123",
    }
    first_response = await client.post("/api/v1/auth/register", json=payload)
    second_response = await client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    audit_messages = [record.message for record in caplog.records if record.name == "app.audit"]
    assert any("audit_event=auth.register_conflict" in message for message in audit_messages)


@pytest.mark.asyncio
async def test_protected_route_requires_bearer_token(client):
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing bearer token."


@pytest.mark.asyncio
async def test_invalid_bearer_token_is_rejected(client):
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token."


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_route(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh-only@cognimon.dev",
            "display_name": "Refresh Only",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "refresh-only@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    refresh_token = login_response.json()["refresh_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired access token."


@pytest.mark.asyncio
async def test_access_token_cannot_refresh_session(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "access-only@cognimon.dev",
            "display_name": "Access Only",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "access-only@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    access_token = login_response.json()["access_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired refresh token."


@pytest.mark.asyncio
async def test_password_reset_request_creates_token_for_active_user(client, app):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reset-me@cognimon.dev",
            "display_name": "Reset Me",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    response = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "reset-me@cognimon.dev"},
    )

    assert response.status_code == 202
    assert response.json()["detail"] == (
        "If an active account exists for that email, a reset token has been issued."
    )

    async with app.state.db.session_factory() as session:
        result = await session.execute(select(PasswordResetToken))
        reset_tokens = list(result.scalars().all())
        assert len(reset_tokens) == 1
        assert reset_tokens[0].token_hash
        assert reset_tokens[0].expires_at is not None


@pytest.mark.asyncio
async def test_password_reset_request_is_neutral_for_missing_user(client, app):
    response = await client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "missing@cognimon.dev"},
    )

    assert response.status_code == 202
    assert response.json()["detail"] == (
        "If an active account exists for that email, a reset token has been issued."
    )

    async with app.state.db.session_factory() as session:
        result = await session.execute(select(PasswordResetToken))
        reset_tokens = list(result.scalars().all())
        assert reset_tokens == []


@pytest.mark.asyncio
async def test_password_reset_confirm_updates_password_and_consumes_token(client, app):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "confirm-reset@cognimon.dev",
            "display_name": "Confirm Reset",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    raw_reset_token = generate_password_reset_token()

    async with app.state.db.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "confirm-reset@cognimon.dev"))
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_reset_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await session.commit()

    confirm_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_reset_token,
            "new_password": "NewStrongPass123",
        },
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["detail"] == "Password reset completed successfully."

    old_login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "confirm-reset@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    assert old_login_response.status_code == 401

    new_login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "confirm-reset@cognimon.dev",
            "password": "NewStrongPass123",
        },
    )
    assert new_login_response.status_code == 200

    async with app.state.db.session_factory() as session:
        result = await session.execute(select(PasswordResetToken))
        reset_tokens = list(result.scalars().all())
        assert len(reset_tokens) == 1
        assert reset_tokens[0].consumed_at is not None


@pytest.mark.asyncio
async def test_password_reset_confirm_rejects_reuse(client, app):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "confirm-once@cognimon.dev",
            "display_name": "Confirm Once",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    raw_reset_token = generate_password_reset_token()

    async with app.state.db.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "confirm-once@cognimon.dev"))
        session.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hash_password_reset_token(raw_reset_token),
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        await session.commit()

    first_confirm_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_reset_token,
            "new_password": "NewStrongPass123",
        },
    )
    assert first_confirm_response.status_code == 200

    second_confirm_response = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": raw_reset_token,
            "new_password": "AnotherStrongPass123",
        },
    )
    assert second_confirm_response.status_code == 401
    assert second_confirm_response.json()["detail"] == "Invalid or expired password reset token."


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client):
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@cognimon.dev",
            "display_name": "Logout User",
            "password": "StrongPass123",
        },
    )
    assert register_response.status_code == 201

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "logout@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    refresh_token = login_response.json()["refresh_token"]

    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 200
    assert logout_response.json()["detail"] == "Refresh token revoked."

    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401
    assert refresh_response.json()["detail"] == "Refresh token has been revoked."


@pytest.mark.asyncio
async def test_duplicate_registration_is_rejected(client):
    payload = {
        "email": "duplicate@cognimon.dev",
        "display_name": "Duplicate User",
        "password": "StrongPass123",
    }
    first_response = await client.post("/api/v1/auth/register", json=payload)
    second_response = await client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_inactive_user_token_is_rejected(client, app):
    async with app.state.db.session_factory() as session:
        inactive_user = User(
            email="inactive@cognimon.dev",
            display_name="Inactive User",
            password_hash="hashed",
            role=UserRole.learner,
            is_active=False,
        )
        session.add(inactive_user)
        await session.commit()
        await session.refresh(inactive_user)

    token = create_access_token(
        subject=inactive_user.id,
        email=inactive_user.email,
        role=inactive_user.role.value,
        secret=app.state.settings.jwt_secret,
        algorithm=app.state.settings.jwt_algorithm,
        expires_in_minutes=app.state.settings.access_token_expire_minutes,
    )
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User could not be authenticated."


@pytest.mark.asyncio
async def test_inactive_user_refresh_token_is_rejected(client, app):
    async with app.state.db.session_factory() as session:
        inactive_user = User(
            email="inactive-refresh@cognimon.dev",
            display_name="Inactive Refresh User",
            password_hash="hashed",
            role=UserRole.learner,
            is_active=False,
        )
        session.add(inactive_user)
        await session.commit()
        await session.refresh(inactive_user)

    refresh_token = create_refresh_token(
        subject=inactive_user.id,
        email=inactive_user.email,
        role=inactive_user.role.value,
        secret=app.state.settings.refresh_token_secret or app.state.settings.jwt_secret,
        algorithm=app.state.settings.jwt_algorithm,
        expires_in_days=app.state.settings.refresh_token_expire_days,
    )
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "User could not be authenticated."


@pytest.mark.asyncio
async def test_login_rehashes_legacy_password_hash(client, app):
    legacy_user_password = "LegacyPass123"
    async with app.state.db.session_factory() as session:
        legacy_user = User(
            email="legacy-user@cognimon.dev",
            display_name="Legacy User",
            password_hash=hash_password(legacy_user_password),
            role=UserRole.learner,
        )
        session.add(legacy_user)
        await session.commit()
        await session.refresh(legacy_user)
        legacy_hash_before_login = legacy_user.password_hash

    app.state.settings.password_pepper = "login-pepper"

    async with app.state.db.session_factory() as session:
        user_to_upgrade = await session.get(User, legacy_user.id)
        user_to_upgrade.password_hash = hash_password(legacy_user_password, pepper="")
        await session.commit()

    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": legacy_user.email,
            "password": legacy_user_password,
        },
    )

    assert login_response.status_code == 200

    async with app.state.db.session_factory() as session:
        upgraded_user = await session.get(User, legacy_user.id)
        assert upgraded_user.password_hash != legacy_hash_before_login
        assert verify_password(
            legacy_user_password,
            upgraded_user.password_hash,
            pepper="login-pepper",
        )
        assert not verify_password(
            legacy_user_password,
            upgraded_user.password_hash,
            pepper="",
        )


@pytest.mark.asyncio
async def test_admin_route_enforces_rbac(client, admin_user):
    learner_register = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-admin@cognimon.dev",
            "display_name": "Not Admin",
            "password": "StrongPass123",
        },
    )
    assert learner_register.status_code == 201

    learner_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "not-admin@cognimon.dev",
            "password": "StrongPass123",
        },
    )
    learner_token = learner_login.json()["access_token"]

    forbidden_response = await client.get(
        "/api/v1/users/admin",
        headers={"Authorization": f"Bearer {learner_token}"},
    )
    assert forbidden_response.status_code == 403

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": admin_user.email,
            "password": "AdminPass123",
        },
    )
    admin_token = admin_login.json()["access_token"]

    admin_response = await client.get(
        "/api/v1/users/admin",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_response.status_code == 200
    assert admin_response.json()["count"] >= 1
