from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserRole


class UserRepository:
    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, user_id: str) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(
        self,
        session: AsyncSession,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        role: UserRole,
    ) -> User:
        user = User(
            email=email.lower(),
            display_name=display_name,
            password_hash=password_hash,
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    async def record_successful_login(
        self,
        session: AsyncSession,
        user: User,
        *,
        password_hash: str | None = None,
    ) -> User:
        if password_hash is not None:
            user.password_hash = password_hash
        user.last_login_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(user)
        return user

    async def update_password(
        self,
        session: AsyncSession,
        user: User,
        *,
        password_hash: str,
    ) -> User:
        user.password_hash = password_hash
        await session.commit()
        await session.refresh(user)
        return user

    async def list_users(self, session: AsyncSession) -> list[User]:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        return list(result.scalars().all())

