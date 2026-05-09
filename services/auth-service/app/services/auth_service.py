from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
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
    ) -> None:
        self.user_repository = user_repository
        self.event_publisher = event_publisher

    async def register_user(self, session: AsyncSession, payload: RegisterRequest) -> User:
        existing_user = await self.user_repository.get_by_email(session, payload.email)
        if existing_user is not None:
            raise ConflictError("A user with that email already exists.")

        user = await self.user_repository.create_user(
            session,
            email=payload.email,
            display_name=payload.display_name,
            password_hash=hash_password(payload.password),
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
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password.")
        if not user.is_active:
            raise AuthenticationError("This account is inactive.")
        return await self.user_repository.update_last_login(session, user)

    def issue_access_token(self, user: User, settings: Settings) -> str:
        return create_access_token(
            subject=user.id,
            email=user.email,
            role=user.role.value,
            secret=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            expires_in_minutes=settings.access_token_expire_minutes,
        )

