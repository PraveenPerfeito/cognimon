from pathlib import Path

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import hash_password
from app.db.models import User, UserRole
from app.main import create_app


@pytest_asyncio.fixture
async def app():
    database_file = Path(__file__).parent / "auth-service-test.db"
    if database_file.exists():
        database_file.unlink()

    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{database_file.as_posix()}",
        jwt_secret="test-secret-key-please-change-123",
        allowed_origins=["http://testserver"],
        bootstrap_schema=False,
    )
    application = create_app(settings)
    await application.state.db.create_schema()
    yield application
    await application.state.db.dispose()
    if database_file.exists():
        database_file.unlink()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as http_client:
        yield http_client


@pytest_asyncio.fixture
async def admin_user(app):
    async with app.state.db.session_factory() as session:
        admin = User(
            email="admin@cognimon.dev",
            display_name="Admin Trainer",
            password_hash=hash_password("AdminPass123"),
            role=UserRole.admin,
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        return admin
