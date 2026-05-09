from collections.abc import AsyncIterator, Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.db.models import User, UserRole
from app.messaging.noop import NoopAuthEventPublisher
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.db.session_factory
    async with session_factory() as session:
        yield session


def get_auth_service() -> AuthService:
    return AuthService(
        user_repository=UserRepository(),
        event_publisher=NoopAuthEventPublisher(),
    )


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing bearer token.")

    payload = decode_access_token(
        token=credentials.credentials,
        secret=settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Malformed token payload.")

    user = await UserRepository().get_by_id(session, subject)
    if user is None or not user.is_active:
        raise AuthenticationError("User could not be authenticated.")
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


def as_http_exception(exc: AuthenticationError | AuthorizationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc),
        headers={"WWW-Authenticate": "Bearer"},
    )
