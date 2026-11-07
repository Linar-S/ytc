"""Database queries for videos."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video


async def get_by_id(session: AsyncSession, video_id: uuid.UUID) -> Video | None:
    """Return a video by primary key."""

    return await session.get(Video, video_id)


async def get_for_owner(
    session: AsyncSession,
    video_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Video | None:
    """Return a video only when it belongs to the given owner."""

    return await session.scalar(
        select(Video).where(Video.id == video_id, Video.owner_id == owner_id)
    )


def add_video(session: AsyncSession, video: Video) -> Video:
    """Stage a video record for insertion."""

    session.add(video)
    return video
