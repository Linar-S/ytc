"""Database queries for likes."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Like


async def get_like(session: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> Like | None:
    """Return a like for a user/video pair, if present."""

    return await session.scalar(
        select(Like).where(Like.user_id == user_id, Like.video_id == video_id)
    )


def add_like(session: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> Like:
    """Stage a new like row."""

    like = Like(user_id=user_id, video_id=video_id)
    session.add(like)
    return like


async def delete_like(session: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> None:
    """Delete a like row if it exists (idempotent)."""

    await session.execute(delete(Like).where(Like.user_id == user_id, Like.video_id == video_id))


async def count_for_video(session: AsyncSession, video_id: uuid.UUID) -> int:
    """Count likes for one video."""

    value = await session.scalar(select(func.count(Like.id)).where(Like.video_id == video_id))
    return int(value or 0)


async def is_liked(session: AsyncSession, user_id: uuid.UUID, video_id: uuid.UUID) -> bool:
    """Return whether a user liked a video."""

    return (
        await session.scalar(
            select(Like.id).where(Like.user_id == user_id, Like.video_id == video_id)
        )
        is not None
    )


async def counts_for_videos(
    session: AsyncSession, video_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Aggregate like counts for a batch of videos."""

    if not video_ids:
        return {}
    rows = await session.execute(
        select(Like.video_id, func.count(Like.id))
        .where(Like.video_id.in_(video_ids))
        .group_by(Like.video_id)
    )
    return {video_id: int(count) for video_id, count in rows}
