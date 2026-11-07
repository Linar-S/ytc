"""FastAPI application factory and lifespan management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio

from app.config import settings
from app.database import (
    dispose_engine,
    get_session_factory,
    init_engine,
)
from app.routers import health

logger = logging.getLogger(__name__)


def _create_minio_client() -> Minio:
    """Build a MinIO client from application settings."""

    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize shared resources on startup and release them on shutdown."""

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    db_engine = init_engine()
    app.state.db_engine = db_engine
    app.state.session_factory = get_session_factory()

    try:
        app.state.minio_client = _create_minio_client()
    except Exception:
        # Storage is not required for the basic API to start. Transient MinIO
        # configuration/availability issues must not take the whole app down.
        logger.exception("MinIO client initialization failed")
        app.state.minio_client = None
    app.state.minio_bucket = settings.minio_bucket

    logger.info("Application startup complete")
    try:
        yield
    finally:
        minio_client = getattr(app.state, "minio_client", None)
        app.state.minio_client = None
        if minio_client is not None:
            close = getattr(minio_client, "close", None)
            if callable(close):
                close()

        await dispose_engine()
        logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# /health is deliberately public. Any future router must declare an auth
# dependency (explicitly or at router level).
app.include_router(health.router)
