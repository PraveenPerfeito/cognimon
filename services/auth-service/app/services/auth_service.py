from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_and_rehash_password,
)
from app.db.models import User, UserRole
from app.messaging.contracts import AuthEventPublisher, UserRegisteredEvent
from app.repositories.revoked_refresh_tokens import RevokedRefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest


class AuthService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        revoked_refresh_token_repository: RevokedRefreshTokenRepository,
        event_publisher: AuthEventPublisher,
        password_pepper: str = "",
    ) -> None:
        self.user_repository = user_repository
        self.revoked_refresh_token_repository = revoked_refresh_token_repository
        self.event_publisher = event_publisher
        self.password_pepper = password_pepper

    async def register_user(self, session: AsyncSession, payload: RegisterRequest) -> User:
        existing_user = await self.user_repository.get_by_email(session, payload.email)
        if existing_user is not None:
            raise ConflictError("A user with that email already exists.")

        user = await self.user_repository.create_user(
            session,
            email=payload.email,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password, pepper=self.password_pepper),
            role=UserRole.learner,
        )
        await self.event_publisher.publish_user_registered(
            UserRegisteredEvent(
                user_id=user.id,
                email=user.email,
                role=user.role.value,
            )
        )
        return user

    async def authenticate_user(self, session: AsyncSession, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(session, email)
        if user is None:
            raise AuthenticationError("Invalid email or password.")
        password_is_valid, upgraded_hash = verify_and_rehash_password(
            password,
            user.password_hash,
            pepper=self.password_pepper,
        )
        if not password_is_valid:
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is inactive.")
        return await self.user_repository.record_successful_login(
            session,
            user,
            password_hash=upgraded_hash,
        )

    def issue_access_token(self, user: User, settings: Settings) -> str:
        return create_access_token(
            subject=user.id,
            email=user.email,
            role=user.role.value,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expires_in_minutes=settings.access_token_expire_minutes,
        )

    def issue_refresh_token(self, user: User, settings: Settings) -> str:
        refresh_secret = settings.refresh_token_secret or settings.jwt_secret
        return create_refresh_token(
            subject=user.id,
            email=user.email,
            role=user.role.value,
            secret=refresh_secret,
            algorithm=settings.jwt_algorithm,
            expires_in_days=settings.refresh_token_expire_days,
        )

    async def authenticate_refresh_token(
        self,
        session: AsyncSession,
        refresh_token: str,
        settings: Settings,
    ) -> User:
        refresh_secret = settings.refresh_token_secret or settings.jwt_secret
        claims = decode_refresh_token(
            token=refresh_token,
            secret=refresh_secret,
            algorithm=settings.jwt_algorithm,
        )
        if await self.revoked_refresh_token_repository.is_token_revoked(session, claims.token_id):
            raise AuthenticationError("Refresh token has been revoked.")
        user = await self.user_repository.get_by_id(session, claims.subject)
        if user is None or not user.is_active:
            raise AuthenticationError("User could not be authenticated.")
        return user

    async def revoke_refresh_token(
        self,
        session: AsyncSession,
        refresh_token: str,
        settings: Settings,
    ) -> None:
        refresh_secret = settings.refresh_token_secret or settings.jwt_secret
        claims = decode_refresh_token(
            token=refresh_token,
            secret=refresh_secret,
            algorithm=settings.jwt_algorithm,
        )
        await self.revoked_refresh_token_repository.revoke_token(
            session,
            token_id=claims.token_id,
            user_id=claims.subject,
            expires_at=datetime.fromtimestamp(claims.expires_at, tz=UTC),
        )

