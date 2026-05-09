import pytest


@pytest.mark.asyncio
async def test_health_endpoints(client):
    live_response = await client.get("/api/v1/health/live")
    ready_response = await client.get("/api/v1/health/ready")

    assert live_response.status_code == 200
    assert ready_response.status_code == 200
    assert live_response.json()["service"] == "cognimon-auth-service"
    assert ready_response.json()["status"] == "ready"
