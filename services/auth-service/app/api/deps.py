from collections.abc import AsyncIterator, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, AuthorizationError
from app.db.models import User, UserRole
from app.messaging.noop import NoopAuthEventPublisher
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.db.session_factory
    async with session_factory() as session:
        yield session


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(
        user_repository=UserRepository(),
        event_publisher=NoopAuthEventPublisher(),
        password_pepper=settings.password_pepper,
        audit_log_enabled=settings.audit_log_enabled,
    )


async def get_current_user(
    request: Request,
) -> User:
    user = getattr(request.state, "authenticated_user", None)
    if user is None:
        raise AuthenticationError("Missing bearer token.")
    return user


def require_roles(*allowed_roles: UserRole | str) -> Callable[[User], User]:
    normalized_roles = {
        role.value if isinstance(role, UserRole) else role
        for role in allowed_roles
    }

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        role_value = (
            current_user.role.value
            if isinstance(current_user.role, UserRole)
            else current_user.role
        )
        if role_value not in normalized_roles:
            raise AuthorizationError("You do not have permission to access this resource.")
        return current_user

    return dependency
