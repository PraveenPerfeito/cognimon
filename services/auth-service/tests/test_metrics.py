from pathlib import Path

import pytest

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_request_metrics(client):
    live_response = await client.get("/api/v1/health/live")
    assert live_response.status_code == 200

    unauthorized_response = await client.get("/api/v1/users/me")
    assert unauthorized_response.status_code == 401

    metrics_response = await client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200
    assert metrics_response.headers["content-type"].startswith("text/plain")
    assert "cognimon_auth_service_http_requests_total" in metrics_response.text
    assert 'path="/api/v1/health/live"' in metrics_response.text
    assert 'path="/api/v1/users/me"' in metrics_response.text


@pytest.mark.asyncio
async def test_metrics_endpoint_can_be_disabled():
    database_file = Path(__file__).parent / "auth-service-metrics-disabled.db"
    if database_file.exists():
        database_file.unlink()

    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{database_file.as_posix()}",
        jwt_secret="test-secret-key-please-change-123",
        allowed_origins=["http://testserver"],
        metrics_enabled=False,
        bootstrap_schema=False,
    )
    application = create_app(settings)
    await application.state.db.create_schema()

    try:
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(
            transport=ASGITransport(app=application),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/metrics")
            assert response.status_code == 404
            assert response.json()["detail"] == "Metrics are disabled."
    finally:
        await application.state.db.dispose()
        if database_file.exists():
            database_file.unlink()
