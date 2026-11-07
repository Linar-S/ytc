"""ARQ worker configuration."""

from typing import ClassVar

from arq.connections import RedisSettings

from app.config import settings


class WorkerSettings:
    """Minimal ARQ settings.

    Jobs will be added to ``functions`` as background features are built.
    """

    functions: ClassVar[list] = []
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
