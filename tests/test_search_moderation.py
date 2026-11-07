"""Search, reporting and moderation endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ModerationAction, User, UserRole, Video, VideoStatus, Visibility
from app.services.auth import create_access_token


class FakeMinio:
    def bucket_exists(self, bucket: str) -> bool:
        return True

    def make_bucket(self, bucket: str) -> None:
        return None

    def presigned_get_url(self, bucket: str, object_key: str, expires=None) -> str:
        return f"http://minio.local/{bucket}/{object_key}?GET"

    def presigned_put_url(self, bucket: str, object_key: str, expires=None) -> str:
        return f"http://minio.local/{bucket}/{object_key}?PUT"

    def close(self) -> None:
        return None


@pytest_asyncio.fixture
async def moderation_env() -> AsyncIterator[SimpleNamespace]:
    """Provide owner, moderator, regular user and five reporters."""

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
        owner = User(
            email="owner-mod@example.com",
            username="owner_mod",
            hashed_password="not-used",
        )
        moderator = User(
            email="moderator@example.com",
            username="moderator",
            hashed_password="not-used",
            role=UserRole.MODERATOR,
        )
        regular = User(
            email="regular-mod@example.com",
            username="regular_mod",
            hashed_password="not-used",
        )
        reporters = [
            User(
                email=f"reporter{index}@example.com",
                username=f"reporter{index}",
                hashed_password="not-used",
            )
            for index in range(5)
        ]
        session.add_all([owner, moderator, regular, *reporters])
        await session.commit()
        for user in (owner, moderator, regular, *reporters):
            await session.refresh(user)

        video = Video(
            owner_id=owner.id,
            title="Unique Searchable Video",
            description="A searchable description",
            status=VideoStatus.READY,
            visibility=Visibility.PUBLIC,
            storage_key="videos/searchable.mp4",
            thumbnail_key="thumbnails/searchable.png",
        )
        private_video = Video(
            owner_id=owner.id,
            title="Unique Private Video",
            status=VideoStatus.READY,
            visibility=Visibility.PRIVATE,
            storage_key="videos/private.mp4",
        )
        processing_video = Video(
            owner_id=owner.id,
            title="Unique Processing Video",
            status=VideoStatus.PROCESSING,
            visibility=Visibility.PUBLIC,
            storage_key="videos/processing.mp4",
        )
        session.add_all([video, private_video, processing_video])
        await session.commit()
        await session.refresh(video)
        video_id = video.id
        owner_id = owner.id
        reporter_ids = [reporter.id for reporter in reporters]

    fake_minio = FakeMinio()

    def headers_for(user_id: uuid.UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user_id)}"}

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
                    session_factory=session_factory,
                    video_id=video_id,
                    owner_id=owner_id,
                    owner_headers=headers_for(owner.id),
                    moderator_headers=headers_for(moderator.id),
                    regular_headers=headers_for(regular.id),
                    reporter_headers=[headers_for(reporter_id) for reporter_id in reporter_ids],
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def test_search_only_public_ready(moderation_env: SimpleNamespace) -> None:
    response = await moderation_env.client.get("/search?q=Unique")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Unique Searchable Video"


async def test_regular_user_cannot_access_moderation_queue(
    moderation_env: SimpleNamespace,
) -> None:
    response = await moderation_env.client.get(
        "/moderation/queue", headers=moderation_env.regular_headers
    )
    assert response.status_code == 403


async def test_moderator_hide_removes_video_from_feed_and_search(
    moderation_env: SimpleNamespace,
) -> None:
    report = await moderation_env.client.post(
        f"/videos/{moderation_env.video_id}/report",
        headers=moderation_env.regular_headers,
        json={"reason": "spam"},
    )
    assert report.status_code == 201

    queue = await moderation_env.client.get(
        "/moderation/queue", headers=moderation_env.moderator_headers
    )
    assert queue.status_code == 200
    assert queue.json()["items"][0]["report_count"] == 1

    hidden = await moderation_env.client.post(
        f"/moderation/videos/{moderation_env.video_id}/hide",
        headers=moderation_env.moderator_headers,
    )
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "hidden"

    feed = await moderation_env.client.get("/videos")
    assert feed.json()["total"] == 0
    search = await moderation_env.client.get("/search?q=Unique")
    assert search.json()["total"] == 0

    moderator_view = await moderation_env.client.get(
        f"/videos/{moderation_env.video_id}",
        headers=moderation_env.moderator_headers,
    )
    assert moderator_view.status_code == 200

    regular_view = await moderation_env.client.get(
        f"/videos/{moderation_env.video_id}",
        headers=moderation_env.regular_headers,
    )
    assert regular_view.status_code == 403

    async with moderation_env.session_factory() as session:
        actions = list(await session.scalars(select(ModerationAction)))
        assert len(actions) == 1
        assert actions[0].action == "hide"


async def test_auto_hide_after_five_distinct_reporters(
    moderation_env: SimpleNamespace,
) -> None:
    last_response = None
    for headers in moderation_env.reporter_headers:
        last_response = await moderation_env.client.post(
            f"/videos/{moderation_env.video_id}/report",
            headers=headers,
            json={"reason": "harassment"},
        )
        assert last_response.status_code == 201

    assert last_response is not None
    assert last_response.json()["auto_hidden"] is True
    assert last_response.json()["report_count"] == 5

    feed = await moderation_env.client.get("/videos")
    assert feed.json()["total"] == 0


async def test_report_rate_limit(moderation_env: SimpleNamespace) -> None:
    for _ in range(5):
        response = await moderation_env.client.post(
            f"/videos/{moderation_env.video_id}/report",
            headers=moderation_env.regular_headers,
            json={"reason": "other"},
        )
        assert response.status_code == 201

    limited = await moderation_env.client.post(
        f"/videos/{moderation_env.video_id}/report",
        headers=moderation_env.regular_headers,
        json={"reason": "other"},
    )
    assert limited.status_code == 429
