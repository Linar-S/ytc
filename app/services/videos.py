"""Business logic for direct-to-MinIO video uploads."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, Video, VideoStatus, Visibility
from app.repositories import likes as like_repo
from app.repositories import videos as video_repo
from app.schemas.video import (
    VideoDetailOut,
    VideoFeedItem,
    VideoInitUploadRequest,
    VideoOut,
)
from app.services import storage
from app.services.queue import enqueue_process_video


class VideoUploadError(Exception):
    """Base class for upload workflow failures."""


class InvalidMimeTypeError(VideoUploadError):
    """Raised when the declared upload is not a video."""


class FileTooLargeError(VideoUploadError):
    """Raised when the declared or stored size exceeds the limit."""


class VideoNotFoundError(VideoUploadError):
    """Raised when a video does not exist or is not owned by the caller."""


class UploadedObjectNotFoundError(VideoUploadError):
    """Raised when MinIO does not contain the uploaded object."""


class QueueUnavailableError(VideoUploadError):
    """Raised when the processing task could not be enqueued."""


class AccessDeniedError(VideoUploadError):
    """Raised when a private video is requested by a non-owner."""


@dataclass(frozen=True)
class InitUploadResult:
    """Video row plus presigned upload instructions."""

    video: Video
    upload_url: str
    object_key: str


def _safe_filename(filename: str) -> str:
    """Reduce a client filename to a safe object-key component."""

    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned[:180] or "video.bin"


def build_object_key(owner_id: uuid.UUID, video_id: uuid.UUID, filename: str) -> str:
    """Build a collision-resistant object key for a video file."""

    return f"videos/{owner_id}/{video_id}/{_safe_filename(filename)}"


def validate_video_metadata(content_type: str, file_size: int | None = None) -> None:
    """Validate MIME type and declared file size."""

    if not content_type.lower().startswith("video/"):
        raise InvalidMimeTypeError("Only video/* content types are allowed")
    if file_size is not None and file_size > settings.max_video_size_bytes:
        raise FileTooLargeError("Video exceeds the 2 GB upload limit")


async def init_upload(
    session: AsyncSession,
    owner: User,
    payload: VideoInitUploadRequest,
    minio_client,
    bucket: str,
) -> InitUploadResult:
    """Create an uploading video row and return a presigned PUT URL."""

    validate_video_metadata(payload.content_type, payload.file_size)

    video_id = uuid.uuid4()
    object_key = build_object_key(owner.id, video_id, payload.filename)
    title = payload.title or payload.filename.rsplit(".", 1)[0] or "Untitled video"

    upload_url = await storage.presigned_put_url(
        minio_client,
        bucket,
        object_key,
        expires=timedelta(seconds=settings.upload_url_ttl_seconds),
    )

    video = Video(
        id=video_id,
        owner_id=owner.id,
        title=title[:255],
        description=payload.description,
        status=VideoStatus.UPLOADING,
        visibility=payload.visibility or Visibility.PUBLIC,
        storage_key=object_key,
    )
    video_repo.add_video(session, video)
    await session.commit()
    await session.refresh(video)

    return InitUploadResult(video=video, upload_url=upload_url, object_key=object_key)


async def complete_upload(
    session: AsyncSession,
    owner: User,
    video_id: uuid.UUID,
    minio_client,
    bucket: str,
) -> Video:
    """Verify the MinIO object, move the video to processing and enqueue work."""

    video = await video_repo.get_for_owner(session, video_id, owner.id)
    if video is None:
        raise VideoNotFoundError("Video not found")
    if not video.storage_key:
        raise UploadedObjectNotFoundError("Uploaded object was not found")

    info = await storage.stat_object(minio_client, bucket, video.storage_key)
    if info is None:
        raise UploadedObjectNotFoundError("Uploaded object was not found")

    stored_size = getattr(info, "size", None)
    if stored_size is not None and stored_size > settings.max_video_size_bytes:
        raise FileTooLargeError("Video exceeds the 2 GB upload limit")

    if video.status is VideoStatus.READY:
        return video

    video.status = VideoStatus.PROCESSING
    await session.commit()
    await session.refresh(video)

    try:
        await enqueue_process_video(video.id)
    except Exception as exc:
        video.status = VideoStatus.FAILED
        await session.commit()
        raise QueueUnavailableError("Could not enqueue video processing") from exc

    return video


async def get_playback_url(minio_client, bucket: str, video: Video) -> str | None:
    """Return a presigned GET URL for a ready video."""

    if not video.storage_key:
        return None
    return await storage.presigned_get_url(minio_client, bucket, video.storage_key)


def can_view_video(video: Video, user: User | None) -> bool:
    """Apply visibility rules for direct video/comments access."""

    if video.visibility is Visibility.PRIVATE:
        return user is not None and user.id == video.owner_id
    return True


async def get_video_for_view(
    session: AsyncSession,
    video_id: uuid.UUID,
    user: User | None,
) -> Video:
    """Load a video and enforce private-video access rules."""

    video = await video_repo.get_with_owner(session, video_id)
    if video is None:
        raise VideoNotFoundError("Video not found")
    if not can_view_video(video, user):
        raise AccessDeniedError("Access denied")
    return video


async def _get_url(
    client,
    bucket: str,
    object_key: str | None,
) -> str | None:
    """Return a presigned GET URL when a client and key are available."""

    if client is None or not object_key:
        return None
    return await storage.presigned_get_url(
        client,
        bucket,
        object_key,
        expires=timedelta(seconds=settings.playback_url_ttl_seconds),
    )


async def list_feed(
    session: AsyncSession,
    page: int,
    size: int,
    minio_client,
    bucket: str,
) -> tuple[list[VideoFeedItem], int]:
    """Return a paginated public-ready feed with thumbnails and like counts."""

    offset = (page - 1) * size
    videos = await video_repo.list_public_ready(session, offset, size)
    total = await video_repo.count_public_ready(session)
    counts = await like_repo.counts_for_videos(session, [video.id for video in videos])

    items: list[VideoFeedItem] = []
    for video in videos:
        base = VideoOut.model_validate(video).model_dump()
        items.append(
            VideoFeedItem(
                **base,
                owner_username=video.owner.username if video.owner else None,
                thumbnail_url=await _get_url(minio_client, bucket, video.thumbnail_key),
                like_count=counts.get(video.id, 0),
            )
        )
    return items, total


async def get_video_detail(
    session: AsyncSession,
    video_id: uuid.UUID,
    user: User | None,
    minio_client,
    bucket: str,
) -> VideoDetailOut:
    """Return video metadata, playback URL and per-user like state."""

    video = await get_video_for_view(session, video_id, user)
    base = VideoOut.model_validate(video).model_dump()
    playback_url = None
    if video.status is VideoStatus.READY:
        playback_url = await _get_url(minio_client, bucket, video.storage_key)

    like_count = await like_repo.count_for_video(session, video.id)
    liked = False
    if user is not None:
        liked = await like_repo.is_liked(session, user.id, video.id)

    return VideoDetailOut(
        **base,
        owner_username=video.owner.username if video.owner else None,
        thumbnail_url=await _get_url(minio_client, bucket, video.thumbnail_key),
        like_count=like_count,
        playback_url=playback_url,
        liked=liked,
    )
