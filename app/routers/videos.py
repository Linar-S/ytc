"""Video upload, feed, playback and social endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_current_user
from app.models import User
from app.schemas.comment import CommentCreate, CommentOut, PaginatedComments
from app.schemas.moderation import VideoReportCreate, VideoReportResponse
from app.schemas.video import (
    LikeStatusResponse,
    PaginatedVideos,
    VideoAccessRequest,
    VideoAccessResponse,
    VideoDetailOut,
    VideoInitUploadRequest,
    VideoInitUploadResponse,
    VideoOut,
)
from app.services import moderation as moderation_service
from app.services import social as social_service
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


def _optional_minio_client(request: Request):
    return getattr(request.app.state, "minio_public_client", None) or getattr(
        request.app.state, "minio_client", None
    )


def _bucket(request: Request) -> str:
    return getattr(request.app.state, "minio_bucket", settings.minio_bucket)


def _raise_video_lookup_error(exc: Exception) -> None:
    if isinstance(exc, video_service.VideoNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, video_service.AccessDeniedError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    raise exc


@router.get("", response_model=PaginatedVideos)
async def list_videos(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedVideos:
    """Return only public, ready videos ordered newest first."""

    items, total = await video_service.list_feed(
        session,
        page,
        size,
        _optional_minio_client(request),
        _bucket(request),
    )
    return PaginatedVideos(items=items, total=total, page=page)


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


@router.get("/{video_id}", response_model=VideoDetailOut)
async def get_video(
    video_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
) -> VideoDetailOut:
    """Return video metadata plus a 6-hour presigned playback URL."""

    try:
        return await video_service.get_video_detail(
            session,
            video_id,
            current_user,
            _optional_minio_client(request),
            _bucket(request),
        )
    except (video_service.VideoNotFoundError, video_service.AccessDeniedError) as exc:
        _raise_video_lookup_error(exc)
        raise  # pragma: no cover


@router.post("/{video_id}/like", response_model=LikeStatusResponse)
async def like_video(
    video_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LikeStatusResponse:
    """Idempotently like a video."""

    try:
        await video_service.get_video_for_view(session, video_id, current_user)
    except (video_service.VideoNotFoundError, video_service.AccessDeniedError) as exc:
        _raise_video_lookup_error(exc)
        raise  # pragma: no cover

    liked, like_count = await social_service.like_video(session, current_user.id, video_id)
    return LikeStatusResponse(liked=liked, like_count=like_count)


@router.delete("/{video_id}/like", response_model=LikeStatusResponse)
async def unlike_video(
    video_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LikeStatusResponse:
    """Idempotently remove a like from a video."""

    try:
        await video_service.get_video_for_view(session, video_id, current_user)
    except (video_service.VideoNotFoundError, video_service.AccessDeniedError) as exc:
        _raise_video_lookup_error(exc)
        raise  # pragma: no cover

    liked, like_count = await social_service.unlike_video(session, current_user.id, video_id)
    return LikeStatusResponse(liked=liked, like_count=like_count)


@router.get("/{video_id}/comments", response_model=PaginatedComments)
async def list_comments(
    video_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedComments:
    """Return a newest-first page of comments."""

    try:
        await video_service.get_video_for_view(session, video_id, current_user)
    except (video_service.VideoNotFoundError, video_service.AccessDeniedError) as exc:
        _raise_video_lookup_error(exc)
        raise  # pragma: no cover

    items, total = await social_service.list_comments(session, video_id, page, size)
    return PaginatedComments(items=items, total=total, page=page)


@router.post(
    "/{video_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment(
    video_id: uuid.UUID,
    payload: CommentCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CommentOut:
    """Add a comment to a video (auth required)."""

    try:
        await video_service.get_video_for_view(session, video_id, current_user)
    except (video_service.VideoNotFoundError, video_service.AccessDeniedError) as exc:
        _raise_video_lookup_error(exc)
        raise  # pragma: no cover

    return await social_service.create_comment(
        session,
        video_id,
        current_user,
        payload.content,
    )


@router.post("/{video_id}/access", response_model=VideoAccessResponse)
async def grant_video_access(
    video_id: uuid.UUID,
    payload: VideoAccessRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VideoAccessResponse:
    """Allow one user to view a private video (owner only)."""

    try:
        await video_service.grant_video_access(session, current_user, video_id, payload.user_id)
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except video_service.TargetUserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except video_service.AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return VideoAccessResponse(video_id=video_id, user_id=payload.user_id, granted=True)


@router.delete("/{video_id}/access", response_model=VideoAccessResponse)
async def revoke_video_access(
    video_id: uuid.UUID,
    payload: VideoAccessRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VideoAccessResponse:
    """Remove one user's access to a private video (owner only)."""

    try:
        await video_service.revoke_video_access(session, current_user, video_id, payload.user_id)
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except video_service.AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return VideoAccessResponse(video_id=video_id, user_id=payload.user_id, granted=False)


@router.delete("/{video_id}/access/{user_id}", response_model=VideoAccessResponse)
async def revoke_video_access_by_path(
    video_id: uuid.UUID,
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VideoAccessResponse:
    """Path-parameter alias for revoking private-video access."""

    try:
        await video_service.revoke_video_access(session, current_user, video_id, user_id)
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except video_service.AccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    return VideoAccessResponse(video_id=video_id, user_id=user_id, granted=False)


@router.post(
    "/{video_id}/report",
    response_model=VideoReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_video(
    video_id: uuid.UUID,
    payload: VideoReportCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> VideoReportResponse:
    """Report a video; auto-hides it after five distinct reporters."""

    try:
        result = await moderation_service.report_video(
            session, current_user, video_id, payload.reason
        )
    except video_service.VideoNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except moderation_service.RateLimitExceededError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    return VideoReportResponse(
        id=result.report.id,
        video_id=video_id,
        reason=payload.reason,
        report_count=result.report_count,
        auto_hidden=result.auto_hidden,
    )
