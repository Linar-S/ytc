"""ARQ queue producer helpers."""

from __future__ import annotations

import inspect
import uuid

from arq.connections import RedisSettings, create_pool

from app.config import settings


async def _close_pool(pool) -> None:
    """Close an ARQ/Redis pool across redis-py versions."""

    close = getattr(pool, "aclose", None) or getattr(pool, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def enqueue_process_video(video_id: uuid.UUID) -> str | None:
    """Enqueue the post-upload processing task in Redis via ARQ."""

    pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        job = await pool.enqueue_job("process_video", str(video_id))
        return getattr(job, "job_id", None)
    finally:
        await _close_pool(pool)
