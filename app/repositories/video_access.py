"""Database queries for explicit private-video grants."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VideoAccess


async def has_access(session: AsyncSession, video_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Return whether a user has an explicit grant for a video."""

    return (
        await session.scalar(
            select(VideoAccess.id).where(
                VideoAccess.video_id == video_id,
                VideoAccess.user_id == user_id,
            )
        )
        is not None
    )


def add_access(session: AsyncSession, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoAccess:
    """Stage a new video access grant."""

    access = VideoAccess(video_id=video_id, user_id=user_id)
    session.add(access)
    return access


async def remove_access(session: AsyncSession, video_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Remove a grant if it exists (idempotent)."""

    await session.execute(
        delete(VideoAccess).where(
            VideoAccess.video_id == video_id,
            VideoAccess.user_id == user_id,
        )
    )
