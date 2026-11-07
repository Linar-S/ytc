"""FastAPI application factory and lifespan management."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import (
    dispose_engine,
    get_session_factory,
    init_engine,
)
from app.routers import auth, health, pages, videos
from app.services import storage

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _create_minio_client(endpoint: str | None = None):
    """Build a MinIO client from application settings."""

    return storage.create_minio_client(endpoint)


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
        internal_client = _create_minio_client()
        public_client = _create_minio_client(settings.minio_public_endpoint)
        await storage.ensure_bucket(internal_client, settings.minio_bucket)
        app.state.minio_client = internal_client
        app.state.minio_public_client = public_client
    except Exception:
        # Storage is not required for the basic API to start. Transient MinIO
        # configuration/availability issues must not take the whole app down.
        logger.exception("MinIO initialization failed")
        app.state.minio_client = None
        app.state.minio_public_client = None
    app.state.minio_bucket = settings.minio_bucket

    logger.info("Application startup complete")
    try:
        yield
    finally:
        for attr in ("minio_client", "minio_public_client"):
            client = getattr(app.state, attr, None)
            setattr(app.state, attr, None)
            if client is not None:
                close = getattr(client, "close", None)
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

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(pages.router)
