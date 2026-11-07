"""Public video search endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.video import PaginatedVideos
from app.services import videos as video_service

router = APIRouter(tags=["search"])


def _optional_minio_client(request: Request):
    return getattr(request.app.state, "minio_public_client", None) or getattr(
        request.app.state, "minio_client", None
    )


def _bucket(request: Request) -> str:
    return getattr(request.app.state, "minio_bucket", settings.minio_bucket)


@router.get("/search", response_model=PaginatedVideos)
async def search_videos(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    q: Annotated[str, Query(min_length=1, max_length=200)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedVideos:
    """Search public ready videos by title and description."""

    items, total = await video_service.search_videos(
        session,
        q,
        page,
        size,
        _optional_minio_client(request),
        _bucket(request),
    )
    return PaginatedVideos(items=items, total=total, page=page)
