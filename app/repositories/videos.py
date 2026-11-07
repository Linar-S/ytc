"""Database queries for videos."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Video, VideoStatus, Visibility


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


async def get_with_owner(session: AsyncSession, video_id: uuid.UUID) -> Video | None:
    """Return a video with its owner relationship eagerly loaded."""

    return await session.scalar(
        select(Video).options(selectinload(Video.owner)).where(Video.id == video_id)
    )


async def list_public_ready(session: AsyncSession, offset: int, limit: int) -> list[Video]:
    """Return the public ready feed, newest first."""

    result = await session.scalars(
        select(Video)
        .options(selectinload(Video.owner))
        .where(
            Video.visibility == Visibility.PUBLIC,
            Video.status == VideoStatus.READY,
        )
        .order_by(Video.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result)


async def count_public_ready(session: AsyncSession) -> int:
    """Count videos eligible for the public feed."""

    value = await session.scalar(
        select(func.count(Video.id)).where(
            Video.visibility == Visibility.PUBLIC,
            Video.status == VideoStatus.READY,
        )
    )
    return int(value or 0)
