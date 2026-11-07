"""Database queries for comments."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment


async def list_for_video(
    session: AsyncSession,
    video_id: uuid.UUID,
    offset: int,
    limit: int,
) -> list[Comment]:
    """Return a page of comments, newest first, with authors loaded."""

    result = await session.scalars(
        select(Comment)
        .options(selectinload(Comment.author))
        .where(Comment.video_id == video_id)
        .order_by(Comment.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(result)


async def count_for_video(session: AsyncSession, video_id: uuid.UUID) -> int:
    """Count comments for one video."""

    value = await session.scalar(select(func.count(Comment.id)).where(Comment.video_id == video_id))
    return int(value or 0)


def add_comment(session: AsyncSession, comment: Comment) -> Comment:
    """Stage a new comment row."""

    session.add(comment)
    return comment
