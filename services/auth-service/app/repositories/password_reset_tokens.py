from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PasswordResetToken


class PasswordResetTokenRepository:
    async def get_by_token_hash(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> PasswordResetToken | None:
        result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def create_token(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
    ) -> PasswordResetToken:
        password_reset_token = PasswordResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(password_reset_token)
        await session.commit()
        await session.refresh(password_reset_token)
        return password_reset_token

    async def consume_token(
        self,
        session: AsyncSession,
        password_reset_token: PasswordResetToken,
    ) -> PasswordResetToken:
        password_reset_token.consumed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(password_reset_token)
        return password_reset_token
