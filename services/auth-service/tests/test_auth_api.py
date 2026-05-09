import pytest


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
