"""Video upload API and worker tests with mocked MinIO/ARQ boundaries."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Video, VideoStatus
from app.services import storage
from app.services import videos as video_service
from app.services.auth import create_access_token
from app.workers import tasks as worker_tasks


class FakeMinio:
    """Small synchronous fake matching the MinIO SDK surface used by the app."""

    def __init__(self) -> None:
        self.uploads: dict[str, bytes] = {}
        self.presigned_ttls: list = []

    def bucket_exists(self, bucket: str) -> bool:
        return True

    def make_bucket(self, bucket: str) -> None:
        return None

    def presigned_put_url(self, bucket: str, object_key: str, expires=None) -> str:
        self.presigned_ttls.append(expires)
        return f"http://minio.local/{bucket}/{object_key}?method=PUT"

    def presigned_get_url(self, bucket: str, object_key: str, expires=None) -> str:
        self.presigned_ttls.append(expires)
        return f"http://minio.local/{bucket}/{object_key}?method=GET"

    def put_object(
        self,
        bucket: str,
        object_key: str,
        data,
        length: int,
        content_type: str | None = None,
    ) -> None:
        self.uploads[object_key] = data.read()

    def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def video_env(monkeypatch) -> AsyncIterator[SimpleNamespace]:
    """Provide a DB-backed client, user token, fake MinIO and recorded enqueues."""

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        user = User(
            email="uploader@example.com",
            username="uploader",
            hashed_password="not-used-in-these-tests",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    token = create_access_token(user_id)
    fake_minio = FakeMinio()
    enqueued: list = []

    async def fake_enqueue(video_id) -> str:
        enqueued.append(video_id)
        return "job-1"

    monkeypatch.setattr(video_service, "enqueue_process_video", fake_enqueue)

    async def override_get_db() -> AsyncIterator:
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with app.router.lifespan_context(app):
            app.state.minio_client = fake_minio
            app.state.minio_public_client = fake_minio
            app.state.minio_bucket = "youtube"
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield SimpleNamespace(
                    client=client,
                    headers={"Authorization": f"Bearer {token}"},
                    session_factory=session_factory,
                    minio=fake_minio,
                    enqueued=enqueued,
                    user_id=user_id,
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def _init_upload(env: SimpleNamespace) -> dict:
    response = await env.client.post(
        "/videos/init-upload",
        headers=env.headers,
        json={
            "filename": "demo.mp4",
            "content_type": "video/mp4",
            "file_size": 1024,
            "title": "Demo video",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_init_upload_requires_auth(video_env: SimpleNamespace) -> None:
    response = await video_env.client.post(
        "/videos/init-upload",
        json={
            "filename": "demo.mp4",
            "content_type": "video/mp4",
            "file_size": 1024,
        },
    )
    assert response.status_code == 401


async def test_init_upload_rejects_non_video_mime(video_env: SimpleNamespace) -> None:
    response = await video_env.client.post(
        "/videos/init-upload",
        headers=video_env.headers,
        json={
            "filename": "notes.txt",
            "content_type": "text/plain",
            "file_size": 10,
        },
    )
    assert response.status_code == 400
    assert "video" in response.json()["detail"].lower()


async def test_init_upload_rejects_oversized_declared_file(
    video_env: SimpleNamespace,
) -> None:
    response = await video_env.client.post(
        "/videos/init-upload",
        headers=video_env.headers,
        json={
            "filename": "huge.mp4",
            "content_type": "video/mp4",
            "file_size": 2 * 1024**3 + 1,
        },
    )
    assert response.status_code == 400


async def test_complete_upload_missing_object_returns_404(
    video_env: SimpleNamespace, monkeypatch
) -> None:
    init_data = await _init_upload(video_env)
    monkeypatch.setattr(storage, "stat_object", AsyncMock(return_value=None))

    response = await video_env.client.post(
        f"/videos/{init_data['video_id']}/complete-upload",
        headers=video_env.headers,
    )
    assert response.status_code == 404


async def test_full_upload_cycle_marks_video_ready(video_env: SimpleNamespace, monkeypatch) -> None:
    init_data = await _init_upload(video_env)
    assert init_data["upload_url"].startswith("http://minio.local/")
    assert init_data["object_key"].startswith("videos/")
    assert init_data["expires_in"] == 3600

    monkeypatch.setattr(
        storage,
        "stat_object",
        AsyncMock(return_value=SimpleNamespace(size=1024)),
    )

    completed = await video_env.client.post(
        f"/videos/{init_data['video_id']}/complete-upload",
        headers=video_env.headers,
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "processing"
    assert len(video_env.enqueued) == 1

    monkeypatch.setattr(worker_tasks, "PROCESS_VIDEO_DELAY_SECONDS", 0)
    await worker_tasks.process_video(
        {
            "session_factory": video_env.session_factory,
            "minio_client": video_env.minio,
            "minio_bucket": "youtube",
        },
        init_data["video_id"],
    )

    async with video_env.session_factory() as session:
        video = await session.scalar(
            select(Video).where(Video.id == uuid.UUID(init_data["video_id"]))
        )
        assert video is not None
        assert video.status is VideoStatus.READY
        assert video.thumbnail_key == f"thumbnails/{video.id}.png"
        assert video.thumbnail_key in video_env.minio.uploads

    watch = await video_env.client.get(f"/watch/{init_data['video_id']}")
    assert watch.status_code == 200
    assert "http://minio.local/youtube/videos/" in watch.text
    assert "Demo video" in watch.text
