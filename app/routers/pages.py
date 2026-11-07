"""Jinja2 page routes for the feed, upload and watch UI."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_optional_current_user
from app.models import User
from app.services import social as social_service
from app.services import videos as video_service

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

router = APIRouter(tags=["pages"])


def _optional_minio_client(request: Request):
    return getattr(request.app.state, "minio_public_client", None) or getattr(
        request.app.state, "minio_client", None
    )


def _bucket(request: Request) -> str:
    return getattr(request.app.state, "minio_bucket", settings.minio_bucket)


@router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> HTMLResponse:
    """Render the public video feed."""

    items, total = await video_service.list_feed(
        session,
        1,
        24,
        _optional_minio_client(request),
        _bucket(request),
    )
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"videos": items, "total": total},
    )


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
    """Render a video page with playback, likes and comments."""

    try:
        detail = await video_service.get_video_detail(
            session,
            video_id,
            current_user,
            _optional_minio_client(request),
            _bucket(request),
        )
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except video_service.AccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    comments, comment_total = await social_service.list_comments(session, video_id, 1, 50)

    return templates.TemplateResponse(
        request=request,
        name="watch.html",
        context={
            "video": detail,
            "playback_url": detail.playback_url,
            "thumbnail_url": detail.thumbnail_url,
            "comments": comments,
            "comment_total": comment_total,
        },
    )
