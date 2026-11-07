"""Business logic for likes and comments."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, User
from app.repositories import comments as comment_repo
from app.repositories import likes as like_repo
from app.schemas.comment import CommentOut


def _comment_out(comment: Comment) -> CommentOut:
    """Map a comment with its loaded author to the API schema."""

    author = comment.author if comment.author is not None else None
    return CommentOut(
        id=comment.id,
        video_id=comment.video_id,
        author_id=comment.author_id,
        author_username=author.username if author else None,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


async def like_video(
    session: AsyncSession,
    user_id: uuid.UUID,
    video_id: uuid.UUID,
) -> tuple[bool, int]:
    """Idempotently like a video and return the fresh like count."""

    existing = await like_repo.get_like(session, user_id, video_id)
    if existing is None:
        like_repo.add_like(session, user_id, video_id)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
    return True, await like_repo.count_for_video(session, video_id)


async def unlike_video(
    session: AsyncSession,
    user_id: uuid.UUID,
    video_id: uuid.UUID,
) -> tuple[bool, int]:
    """Idempotently remove a like and return the fresh like count."""

    await like_repo.delete_like(session, user_id, video_id)
    await session.commit()
    return False, await like_repo.count_for_video(session, video_id)


async def list_comments(
    session: AsyncSession,
    video_id: uuid.UUID,
    page: int,
    size: int,
) -> tuple[list[CommentOut], int]:
    """Return a newest-first page of comments and the total count."""

    offset = (page - 1) * size
    comments = await comment_repo.list_for_video(session, video_id, offset, size)
    total = await comment_repo.count_for_video(session, video_id)
    return [_comment_out(comment) for comment in comments], total


async def create_comment(
    session: AsyncSession,
    video_id: uuid.UUID,
    author: User,
    content: str,
) -> CommentOut:
    """Create a comment authored by the current user."""

    comment = Comment(
        video_id=video_id,
        author_id=author.id,
        author=author,
        content=content,
    )
    comment_repo.add_comment(session, comment)
    await session.commit()
    await session.refresh(comment)
    return _comment_out(comment)
