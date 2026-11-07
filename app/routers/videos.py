"""Video upload and processing endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.video import VideoInitUploadRequest, VideoInitUploadResponse, VideoOut
from app.services import videos as video_service

router = APIRouter(prefix="/videos", tags=["videos"])


def _minio_client(request: Request):
    client = getattr(request.app.state, "minio_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is unavailable",
        )
    return client


def _public_minio_client(request: Request):
    client = getattr(request.app.state, "minio_public_client", None)
    if client is None:
        client = getattr(request.app.state, "minio_client", None)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is unavailable",
        )
    return client


def _bucket(request: Request) -> str:
    return getattr(request.app.state, "minio_bucket", settings.minio_bucket)


@router.post(
    "/init-upload",
    response_model=VideoInitUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def init_upload(
    payload: VideoInitUploadRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VideoInitUploadResponse:
    """Reserve an upload and return a presigned PUT URL for direct MinIO upload."""

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            declared_size = None
        if declared_size is not None and declared_size > settings.max_video_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video exceeds the 2 GB upload limit",
            )

    try:
        result = await video_service.init_upload(
            session,
            current_user,
            payload,
            _public_minio_client(request),
            _bucket(request),
        )
    except video_service.InvalidMimeTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except video_service.FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return VideoInitUploadResponse(
        video_id=result.video.id,
        upload_url=result.upload_url,
        object_key=result.object_key,
        expires_in=settings.upload_url_ttl_seconds,
    )


@router.post("/{video_id}/complete-upload", response_model=VideoOut)
async def complete_upload(
    video_id: uuid.UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> VideoOut:
    """Verify the uploaded object and enqueue background processing."""

    try:
        video = await video_service.complete_upload(
            session,
            current_user,
            video_id,
            _minio_client(request),
            _bucket(request),
        )
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except video_service.UploadedObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except video_service.FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except video_service.QueueUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return VideoOut.model_validate(video)
