"""Database queries for refresh tokens."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken


async def add_refresh_token(session: AsyncSession, token: RefreshToken) -> RefreshToken:
    """Stage a refresh-token record for insertion."""

    session.add(token)
    return token


async def get_active_by_jti(session: AsyncSession, jti: str) -> RefreshToken | None:
    """Return a non-revoked refresh-token record by JWT id."""

    return await session.scalar(
        select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.revoked_at.is_(None),
        )
    )


def revoke_token(token: RefreshToken, revoked_at: datetime) -> None:
    """Mark a single refresh-token record as revoked."""

    token.revoked_at = revoked_at


async def revoke_all_for_user(
    session: AsyncSession, user_id: uuid.UUID, revoked_at: datetime
) -> None:
    """Revoke every active refresh token belonging to a user."""

    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=revoked_at)
    )
