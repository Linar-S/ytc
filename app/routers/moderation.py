"""Moderation queue and hide/unhide endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models import User, UserRole
from app.schemas.moderation import ModerationActionResponse, ModerationQueueResponse
from app.services import moderation as moderation_service
from app.services import videos as video_service

router = APIRouter(prefix="/moderation", tags=["moderation"])

Moderator = Annotated[User, Depends(require_role(UserRole.MODERATOR, UserRole.ADMIN))]


@router.get("/queue", response_model=ModerationQueueResponse)
async def get_queue(
    session: Annotated[AsyncSession, Depends(get_db)],
    _moderator: Moderator,
) -> ModerationQueueResponse:
    """Return reported videos sorted by report count."""

    items = await moderation_service.list_moderation_queue(session)
    return ModerationQueueResponse(items=items, total=len(items))


@router.post("/videos/{video_id}/hide", response_model=ModerationActionResponse)
async def hide_video(
    video_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    moderator: Moderator,
) -> ModerationActionResponse:
    """Hide a video from public surfaces."""

    try:
        video = await moderation_service.hide_video(session, moderator, video_id)
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ModerationActionResponse(
        video_id=video.id,
        status=video.status,
        action="hide",
    )


@router.post("/videos/{video_id}/unhide", response_model=ModerationActionResponse)
async def unhide_video(
    video_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    moderator: Moderator,
) -> ModerationActionResponse:
    """Restore a hidden video."""

    try:
        video = await moderation_service.unhide_video(session, moderator, video_id)
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return ModerationActionResponse(
        video_id=video.id,
        status=video.status,
        action="unhide",
    )
