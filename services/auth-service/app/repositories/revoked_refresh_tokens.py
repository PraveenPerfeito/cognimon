from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RevokedRefreshToken


class RevokedRefreshTokenRepository:
    async def is_token_revoked(self, session: AsyncSession, token_id: str) -> bool:
        result = await session.execute(
            select(RevokedRefreshToken.token_id).where(RevokedRefreshToken.token_id == token_id)
        )
        return result.scalar_one_or_none() is not None

    async def revoke_token(
        self,
        session: AsyncSession,
        *,
        token_id: str,
        user_id: str,
        expires_at: datetime,
    ) -> RevokedRefreshToken:
        existing = await session.get(RevokedRefreshToken, token_id)
        if existing is not None:
            return existing

        revoked_token = RevokedRefreshToken(
            token_id=token_id,
            user_id=user_id,
            expires_at=expires_at.astimezone(UTC),
        )
        session.add(revoked_token)
        await session.commit()
        await session.refresh(revoked_token)
        return revoked_token
