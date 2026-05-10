import pytest

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User, UserRole


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

    profile_response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == "learner@cognimon.dev"


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
