import logging

import pytest

from app.api.deps import build_auth_event_publisher
from app.core.config import Settings
from app.messaging.log import LoggingAuthEventPublisher
from app.messaging.noop import NoopAuthEventPublisher


def test_build_auth_event_publisher_supports_noop_backend() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///publisher-noop.db",
        jwt_secret="test-secret-key-please-change-123",
        event_publisher_backend="noop",
    )

    publisher = build_auth_event_publisher(settings)

    assert isinstance(publisher, NoopAuthEventPublisher)


def test_build_auth_event_publisher_supports_logging_backend() -> None:
    settings = Settings(
        environment="test",
        database_url="sqlite+aiosqlite:///publisher-log.db",
        jwt_secret="test-secret-key-please-change-123",
        event_publisher_backend="log",
    )

    publisher = build_auth_event_publisher(settings)

    assert isinstance(publisher, LoggingAuthEventPublisher)


@pytest.mark.asyncio
async def test_register_user_emits_structured_log_event(client, app, caplog) -> None:
    app.state.settings.event_publisher_backend = "log"
    caplog.set_level(logging.INFO, logger="app.messaging.log")

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logger@cognimon.dev",
            "display_name": "Logger User",
            "password": "StrongPass123",
        },
    )

    assert response.status_code == 201
    assert "event_type=user_registered" in caplog.text
    assert "logger@cognimon.dev" in caplog.text
