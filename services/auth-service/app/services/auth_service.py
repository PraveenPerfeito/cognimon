from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_auth_audit_event
from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_password_reset_token,
    hash_password,
    hash_password_reset_token,
    verify_and_rehash_password,
)
from app.db.models import PasswordResetToken, User, UserRole
from app.messaging.contracts import AuthEventPublisher, UserRegisteredEvent
from app.repositories.password_reset_tokens import PasswordResetTokenRepository
from app.repositories.revoked_refresh_tokens import RevokedRefreshTokenRepository
from app.repositories.users import UserRepository
from app.schemas.auth import (
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
)


class AuthService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        password_reset_token_repository: PasswordResetTokenRepository,
        revoked_refresh_token_repository: RevokedRefreshTokenRepository,
        event_publisher: AuthEventPublisher,
        password_pepper: str = "",
        audit_log_enabled: bool = True,
    ) -> None:
        self.user_repository = user_repository
        self.password_reset_token_repository = password_reset_token_repository
        self.revoked_refresh_token_repository = revoked_refresh_token_repository
        self.event_publisher = event_publisher
        self.password_pepper = password_pepper
        self.audit_log_enabled = audit_log_enabled

    def _audit(self, event: str, **fields: str) -> None:
        if not self.audit_log_enabled:
            return
        log_auth_audit_event(event, **fields)

    async def register_user(self, session: AsyncSession, payload: RegisterRequest) -> User:
        existing_user = await self.user_repository.get_by_email(session, payload.email)
        if existing_user is not None:
            self._audit(
                "auth.register_conflict",
                email=payload.email.lower(),
            )
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
        self._audit(
            "auth.register_success",
            email=user.email,
            role=user.role.value,
            user_id=user.id,
        )
        return user

    async def authenticate_user(self, session: AsyncSession, email: str, password: str) -> User:
        user = await self.user_repository.get_by_email(session, email)
        if user is None:
            self._audit(
                "auth.login_failed",
                email=email.lower(),
                reason="user_not_found",
            )
            raise AuthenticationError("Invalid email or password.")
        password_is_valid, upgraded_hash = verify_and_rehash_password(
            password,
            user.password_hash,
            pepper=self.password_pepper,
        )
        if not password_is_valid:
            self._audit(
                "auth.login_failed",
                email=user.email,
                reason="invalid_password",
                user_id=user.id,
            )
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            self._audit(
                "auth.login_failed",
                email=user.email,
                reason="inactive_user",
                user_id=user.id,
            )
            raise AuthenticationError("This account is inactive.")
        authenticated_user = await self.user_repository.record_successful_login(
            session,
            user,
            password_hash=upgraded_hash,
        )
        self._audit(
            "auth.login_success",
            email=authenticated_user.email,
            role=authenticated_user.role.value,
            user_id=authenticated_user.id,
        )
        return authenticated_user

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

    async def request_password_reset(
        self,
        session: AsyncSession,
        payload: PasswordResetRequest,
        settings: Settings,
    ) -> PasswordResetToken | None:
        user = await self.user_repository.get_by_email(session, payload.email)
        if user is None or not user.is_active:
            return None

        reset_token = generate_password_reset_token()
        return await self.password_reset_token_repository.create_token(
            session,
            user_id=user.id,
            token_hash=hash_password_reset_token(reset_token),
            expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )

    async def confirm_password_reset(
        self,
        session: AsyncSession,
        payload: PasswordResetConfirmRequest,
    ) -> User:
        password_reset_token = await self.password_reset_token_repository.get_by_token_hash(
            session,
            hash_password_reset_token(payload.token),
        )
        if password_reset_token is None:
            raise AuthenticationError("Invalid or expired password reset token.")
        if password_reset_token.consumed_at is not None:
            raise AuthenticationError("Invalid or expired password reset token.")
        expires_at = password_reset_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise AuthenticationError("Invalid or expired password reset token.")

        user = await self.user_repository.get_by_id(session, password_reset_token.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("User could not be authenticated.")

        await self.user_repository.update_password(
            session,
            user,
            password_hash=hash_password(payload.new_password, pepper=self.password_pepper),
        )
        await self.password_reset_token_repository.consume_token(session, password_reset_token)
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
