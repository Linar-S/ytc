"""Business logic for direct-to-MinIO video uploads."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User, Video, VideoStatus, Visibility
from app.repositories import videos as video_repo
from app.schemas.video import VideoInitUploadRequest
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
