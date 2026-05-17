import pytest


@pytest.mark.asyncio
async def test_health_endpoints(client):
    live_response = await client.get("/api/v1/health/live")
    ready_response = await client.get("/api/v1/health/ready")

    assert live_response.status_code == 200
    assert ready_response.status_code == 200
    assert live_response.json()["service"] == "cognimon-auth-service"
    assert live_response.json()["environment"] == "test"
    assert live_response.json()["version"] == "0.1.0"
    assert ready_response.json()["status"] == "ready"
    assert ready_response.json()["environment"] == "test"
