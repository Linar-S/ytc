"""ARQ background tasks for video processing."""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from typing import Any

from app.config import settings
from app.database import dispose_engine, get_session_factory, init_engine
from app.models import Video, VideoStatus
from app.services import storage

logger = logging.getLogger(__name__)

PROCESS_VIDEO_DELAY_SECONDS = 2.0

# 1x1 transparent PNG used when ffmpeg is unavailable.
PLACEHOLDER_PREVIEW = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


async def startup(ctx: dict[str, Any]) -> None:
    """Initialize DB pooling and MinIO access for the worker process."""

    init_engine()
    ctx["session_factory"] = get_session_factory()
    client = storage.create_minio_client()
    ctx["minio_client"] = client
    ctx["minio_bucket"] = settings.minio_bucket
    try:
        await storage.ensure_bucket(client, settings.minio_bucket)
    except Exception:
        logger.exception("Worker could not ensure MinIO bucket")


async def shutdown(ctx: dict[str, Any]) -> None:
    """Release worker resources."""

    client = ctx.get("minio_client")
    if client is not None:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    await dispose_engine()


async def process_video(ctx: dict[str, Any], video_id: str) -> None:
    """Finalize an uploaded video and generate a placeholder preview."""

    await asyncio.sleep(PROCESS_VIDEO_DELAY_SECONDS)

    try:
        parsed_video_id = uuid.UUID(str(video_id))
    except (TypeError, ValueError):
        logger.warning("process_video got invalid video id: %r", video_id)
        return

    session_factory = ctx.get("session_factory") or get_session_factory()
    async with session_factory() as session:
        video = await session.get(Video, parsed_video_id)
        if video is None:
            logger.warning("process_video: video %s not found", video_id)
            return

        thumbnail_key = f"thumbnails/{video.id}.png"
        client = ctx.get("minio_client")
        bucket = ctx.get("minio_bucket", settings.minio_bucket)
        if client is not None:
            try:
                await storage.ensure_bucket(client, bucket)
                await storage.put_object(
                    client,
                    bucket,
                    thumbnail_key,
                    PLACEHOLDER_PREVIEW,
                    content_type="image/png",
                )
                video.thumbnail_key = thumbnail_key
            except Exception:
                logger.exception("Could not generate thumbnail for video %s", video_id)

        video.status = VideoStatus.READY
        await session.commit()
        logger.info("Video %s is ready", video_id)
