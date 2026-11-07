"""ARQ worker configuration."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings
from app.workers.tasks import process_video, shutdown, startup


class WorkerSettings:
    """ARQ worker settings for video processing jobs."""

    functions: ClassVar[list] = [process_video]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
