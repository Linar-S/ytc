"""Channel, subscription and private-video access tests."""

from __future__ import annotations

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
async def channel_env() -> AsyncIterator[SimpleNamespace]:
    """Provide three users, tokens and a private video owned by Alice."""

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
            email="alice-channel@example.com",
            username="alice_channel",
            hashed_password="not-used",
        )
        bob = User(
            email="bob-channel@example.com",
            username="bob_channel",
            hashed_password="not-used",
        )
        carol = User(
            email="carol-channel@example.com",
            username="carol_channel",
            hashed_password="not-used",
        )
        session.add_all([alice, bob, carol])
        await session.commit()
        for user in (alice, bob, carol):
            await session.refresh(user)

        video = Video(
            owner_id=alice.id,
            title="Private channel video",
            status=VideoStatus.READY,
            visibility=Visibility.PRIVATE,
            storage_key=f"videos/{alice.id}/private.mp4",
            thumbnail_key=f"thumbnails/{alice.id}.png",
        )
        session.add(video)
        await session.commit()
        await session.refresh(video)
        alice_id, bob_id, carol_id, video_id = (
            alice.id,
            bob.id,
            carol.id,
            video.id,
        )

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
                    alice_id=alice_id,
                    bob_id=bob_id,
                    carol_id=carol_id,
                    video_id=video_id,
                    alice_headers={"Authorization": f"Bearer {create_access_token(alice_id)}"},
                    bob_headers={"Authorization": f"Bearer {create_access_token(bob_id)}"},
                    carol_headers={"Authorization": f"Bearer {create_access_token(carol_id)}"},
                )
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def test_subscription_is_idempotent(channel_env: SimpleNamespace) -> None:
    first = await channel_env.client.post(
        f"/channels/{channel_env.alice_id}/subscribe",
        headers=channel_env.bob_headers,
    )
    second = await channel_env.client.post(
        f"/channels/{channel_env.alice_id}/subscribe",
        headers=channel_env.bob_headers,
    )
    assert first.status_code == 200
    assert second.json() == {"subscribed": True, "subscriber_count": 1}

    first_delete = await channel_env.client.delete(
        f"/channels/{channel_env.alice_id}/subscribe",
        headers=channel_env.bob_headers,
    )
    second_delete = await channel_env.client.delete(
        f"/channels/{channel_env.alice_id}/subscribe",
        headers=channel_env.bob_headers,
    )
    assert first_delete.json() == {"subscribed": False, "subscriber_count": 0}
    assert second_delete.json() == {"subscribed": False, "subscriber_count": 0}


async def test_private_access_grant_allows_only_target_user(
    channel_env: SimpleNamespace,
) -> None:
    video_id = channel_env.video_id

    denied_before = await channel_env.client.get(
        f"/videos/{video_id}", headers=channel_env.bob_headers
    )
    assert denied_before.status_code == 403

    granted = await channel_env.client.post(
        f"/videos/{video_id}/access",
        headers=channel_env.alice_headers,
        json={"user_id": str(channel_env.bob_id)},
    )
    assert granted.status_code == 200
    assert granted.json()["granted"] is True

    allowed = await channel_env.client.get(f"/videos/{video_id}", headers=channel_env.bob_headers)
    assert allowed.status_code == 200
    assert allowed.json()["playback_url"].startswith("http://minio.local/")

    denied_other = await channel_env.client.get(
        f"/videos/{video_id}", headers=channel_env.carol_headers
    )
    assert denied_other.status_code == 403

    revoked = await channel_env.client.request(
        "DELETE",
        f"/videos/{video_id}/access",
        headers=channel_env.alice_headers,
        json={"user_id": str(channel_env.bob_id)},
    )
    assert revoked.status_code == 200
    denied_after = await channel_env.client.get(
        f"/videos/{video_id}", headers=channel_env.bob_headers
    )
    assert denied_after.status_code == 403


async def test_only_owner_can_grant_access(channel_env: SimpleNamespace) -> None:
    response = await channel_env.client.post(
        f"/videos/{channel_env.video_id}/access",
        headers=channel_env.bob_headers,
        json={"user_id": str(channel_env.carol_id)},
    )
    assert response.status_code == 403


async def test_owner_and_granted_user_see_private_video_in_channel(
    channel_env: SimpleNamespace,
) -> None:
    owner_channel = await channel_env.client.get(
        f"/channels/{channel_env.alice_id}",
        headers=channel_env.alice_headers,
    )
    assert owner_channel.status_code == 200
    assert owner_channel.json()["video_count"] == 1
    assert owner_channel.json()["videos"][0]["visibility"] == "private"

    stranger_channel = await channel_env.client.get(
        f"/channels/{channel_env.alice_id}",
        headers=channel_env.carol_headers,
    )
    assert stranger_channel.status_code == 200
    assert stranger_channel.json()["video_count"] == 0

    granted = await channel_env.client.post(
        f"/videos/{channel_env.video_id}/access",
        headers=channel_env.alice_headers,
        json={"user_id": str(channel_env.bob_id)},
    )
    assert granted.status_code == 200

    granted_channel = await channel_env.client.get(
        f"/channels/{channel_env.alice_id}",
        headers=channel_env.bob_headers,
    )
    assert granted_channel.status_code == 200
    assert granted_channel.json()["video_count"] == 1
    assert granted_channel.json()["videos"][0]["id"] == str(channel_env.video_id)
