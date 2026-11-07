"""Jinja2 page routes for the upload and watch UI."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_optional_current_user
from app.models import User, VideoStatus, Visibility
from app.repositories import videos as video_repo
from app.services import storage

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def index_page(request: Request) -> HTMLResponse:
    """Render the landing page."""

    return templates.TemplateResponse(request=request, name="index.html", context={})


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(request: Request) -> HTMLResponse:
    """Render the direct-to-MinIO upload page."""

    return templates.TemplateResponse(request=request, name="upload.html", context={})


@router.get("/watch/{video_id}", response_class=HTMLResponse)
async def watch_page(
    video_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
) -> HTMLResponse:
    """Render a video page and issue a presigned GET URL when allowed."""

    video = await video_repo.get_by_id(session, video_id)
    if video is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
        )

    is_owner = current_user is not None and current_user.id == video.owner_id
    if video.visibility is Visibility.PRIVATE and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    playback_url = None
    thumbnail_url = None
    client = getattr(request.app.state, "minio_public_client", None) or getattr(
        request.app.state, "minio_client", None
    )
    bucket = getattr(request.app.state, "minio_bucket", "youtube")
    if client is not None:
        if video.status is VideoStatus.READY and video.storage_key:
            playback_url = await storage.presigned_get_url(client, bucket, video.storage_key)
        if video.thumbnail_key:
            thumbnail_url = await storage.presigned_get_url(client, bucket, video.thumbnail_key)

    return templates.TemplateResponse(
        request=request,
        name="watch.html",
        context={
            "video": video,
            "playback_url": playback_url,
            "thumbnail_url": thumbnail_url,
        },
    )
