"""Feed, playback, like and comment endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import User, Video, VideoStatus, Visibility
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
async def social_env() -> AsyncIterator[SimpleNamespace]:
    """Provide in-memory DB, two users, tokens and fake MinIO."""

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
        alice = User(
            email="alice-social@example.com",
            username="alice_social",
            hashed_password="not-used",
        )
        bob = User(
            email="bob-social@example.com",
            username="bob_social",
            hashed_password="not-used",
        )
        session.add_all([alice, bob])
        await session.commit()
        await session.refresh(alice)
        await session.refresh(bob)
        alice_id, bob_id = alice.id, bob.id

    fake_minio = FakeMinio()

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
                    alice_id=alice_id,
                    bob_id=bob_id,
                    alice_headers={"Authorization": f"Bearer {create_access_token(alice_id)}"},
                    bob_headers={"Authorization": f"Bearer {create_access_token(bob_id)}"},
                    minio=fake_minio,
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def _create_video(
    env: SimpleNamespace,
    *,
    owner_id: uuid.UUID,
    visibility: Visibility = Visibility.PUBLIC,
    status: VideoStatus = VideoStatus.READY,
    title: str = "Video",
) -> Video:
    async with env.session_factory() as session:
        video = Video(
            owner_id=owner_id,
            title=title,
            status=status,
            visibility=visibility,
            storage_key=f"videos/{uuid.uuid4()}.mp4",
            thumbnail_key=f"thumbnails/{uuid.uuid4()}.png",
        )
        session.add(video)
        await session.commit()
        await session.refresh(video)
        return video


async def test_feed_hides_private_and_not_ready(social_env: SimpleNamespace) -> None:
    public_video = await _create_video(
        social_env, owner_id=social_env.alice_id, title="Public ready"
    )
    await _create_video(
        social_env,
        owner_id=social_env.alice_id,
        visibility=Visibility.PRIVATE,
        title="Private ready",
    )
    await _create_video(
        social_env,
        owner_id=social_env.alice_id,
        status=VideoStatus.PROCESSING,
        title="Public processing",
    )

    response = await social_env.client.get("/videos")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [str(public_video.id)]
    assert body["items"][0]["thumbnail_url"].startswith("http://minio.local/")


async def test_feed_pagination(social_env: SimpleNamespace) -> None:
    for index in range(25):
        await _create_video(
            social_env,
            owner_id=social_env.alice_id,
            title=f"Video {index}",
        )

    first_page = await social_env.client.get("/videos?page=1&size=10")
    assert first_page.status_code == 200
    assert first_page.json()["total"] == 25
    assert first_page.json()["page"] == 1
    assert len(first_page.json()["items"]) == 10

    third_page = await social_env.client.get("/videos?page=3&size=10")
    assert third_page.status_code == 200
    assert len(third_page.json()["items"]) == 5


async def test_like_is_idempotent(social_env: SimpleNamespace) -> None:
    video = await _create_video(social_env, owner_id=social_env.alice_id)

    first = await social_env.client.post(
        f"/videos/{video.id}/like", headers=social_env.alice_headers
    )
    second = await social_env.client.post(
        f"/videos/{video.id}/like", headers=social_env.alice_headers
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == {"liked": True, "like_count": 1}

    detail = await social_env.client.get(f"/videos/{video.id}", headers=social_env.alice_headers)
    assert detail.status_code == 200
    assert detail.json()["like_count"] == 1
    assert detail.json()["liked"] is True

    removed = await social_env.client.delete(
        f"/videos/{video.id}/like", headers=social_env.alice_headers
    )
    removed_again = await social_env.client.delete(
        f"/videos/{video.id}/like", headers=social_env.alice_headers
    )
    assert removed.json() == {"liked": False, "like_count": 0}
    assert removed_again.json() == {"liked": False, "like_count": 0}


async def test_comment_requires_auth_and_can_be_listed(
    social_env: SimpleNamespace,
) -> None:
    video = await _create_video(social_env, owner_id=social_env.alice_id)

    unauthorized = await social_env.client.post(
        f"/videos/{video.id}/comments",
        json={"content": "No token"},
    )
    assert unauthorized.status_code == 401

    created = await social_env.client.post(
        f"/videos/{video.id}/comments",
        headers=social_env.bob_headers,
        json={"content": "Great video!"},
    )
    assert created.status_code == 201
    assert created.json()["content"] == "Great video!"
    assert created.json()["author_username"] == "bob_social"

    listed = await social_env.client.get(f"/videos/{video.id}/comments?page=1&size=20")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["page"] == 1
    assert listed.json()["items"][0]["content"] == "Great video!"


async def test_private_video_access_rules(social_env: SimpleNamespace) -> None:
    video = await _create_video(
        social_env,
        owner_id=social_env.alice_id,
        visibility=Visibility.PRIVATE,
        title="Owner only",
    )

    anonymous = await social_env.client.get(f"/videos/{video.id}")
    assert anonymous.status_code == 403

    other_user = await social_env.client.get(f"/videos/{video.id}", headers=social_env.bob_headers)
    assert other_user.status_code == 403

    owner = await social_env.client.get(f"/videos/{video.id}", headers=social_env.alice_headers)
    assert owner.status_code == 200
    assert owner.json()["playback_url"].startswith("http://minio.local/")
