from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_auth_audit_event
from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_and_rehash_password,
)
from app.db.models import User, UserRole
from app.messaging.contracts import AuthEventPublisher, UserRegisteredEvent
from app.repositories.users import UserRepository
from app.schemas.auth import RegisterRequest


class AuthService:
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        event_publisher: AuthEventPublisher,
        password_pepper: str = "",
        audit_log_enabled: bool = True,
    ) -> None:
        self.user_repository = user_repository
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

