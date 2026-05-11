from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PasswordResetToken


class PasswordResetTokenRepository:
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
