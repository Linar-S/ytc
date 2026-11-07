"""Seed demo users, videos, comments and likes.

Run inside the backend container after migrations:

    docker compose exec backend python scripts/seed_demo.py
"""

from __future__ import annotations

import asyncio
import base64

from sqlalchemy import func, select

from app.config import settings
from app.database import dispose_engine, get_session_factory, init_engine
from app.models import Comment, Like, User, UserRole, Video, VideoStatus, Visibility
from app.repositories import users as user_repo
from app.services import storage
from app.services.auth import hash_password

DEMO_USERS = [
    {
        "email": "admin@example.com",
        "username": "admin_demo",
        "password": "Admin12345!",
        "role": UserRole.ADMIN,
    },
    {
        "email": "moderator@example.com",
        "username": "moderator_demo",
        "password": "Moderator12345!",
        "role": UserRole.MODERATOR,
    },
    {
        "email": "user@example.com",
        "username": "user_demo",
        "password": "User12345!",
        "role": UserRole.USER,
    },
]

DEMO_VIDEOS = [
    (
        "welcome",
        "Добро пожаловать в YouTube-клон",
        "Демонстрационное видео: лента, просмотр, лайки и комментарии.",
    ),
    (
        "presigned-url",
        "Как работает presigned URL",
        "Клиент загружает файл напрямую в MinIO, backend не проксирует байты.",
    ),
    (
        "fastapi",
        "FastAPI за 5 минут",
        "Асинхронный backend на FastAPI + SQLAlchemy 2.0.",
    ),
    (
        "minio",
        "MinIO и S3 API",
        "Presigned PUT и GET URL, bucket policy и хранение объектов.",
    ),
    (
        "arq",
        "ARQ и фоновые задачи",
        "Очередь Redis и воркер для обработки видео и превью.",
    ),
]

PLACEHOLDER_PREVIEW = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
# Minimal MP4-like payload with a valid ftyp box. Enough to demonstrate presigned
# object storage; replace with real media for a production demo.
PLACEHOLDER_VIDEO = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00\x00\x00\x08free" + b"\x00" * 2048
)


async def ensure_user(session, data: dict) -> User:
    """Create or update a demo user with a known password."""

    user = await user_repo.get_by_email(session, data["email"])
    if user is None:
        user = User(
            email=data["email"],
            username=data["username"],
            hashed_password=hash_password(data["password"]),
            role=data["role"],
            is_active=True,
        )
        session.add(user)
    else:
        user.username = data["username"]
        user.hashed_password = hash_password(data["password"])
        user.role = data["role"]
        user.is_active = True
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_video(
    session,
    owner: User,
    index: int,
    slug: str,
    title: str,
    description: str,
    minio_client,
) -> Video:
    """Create/update a demo video and upload its placeholder objects."""

    video = await session.scalar(
        select(Video).where(Video.owner_id == owner.id, Video.title == title)
    )
    storage_key = f"demo/videos/{slug}.mp4"
    thumbnail_key = f"demo/thumbnails/{slug}.png"

    if video is None:
        video = Video(
            owner_id=owner.id,
            title=title,
            description=description,
            status=VideoStatus.READY,
            visibility=Visibility.PUBLIC,
            storage_key=storage_key,
            thumbnail_key=thumbnail_key,
            views_count=index * 17,
        )
        session.add(video)
    else:
        video.description = description
        video.status = VideoStatus.READY
        video.visibility = Visibility.PUBLIC
        video.storage_key = storage_key
        video.thumbnail_key = thumbnail_key

    await session.commit()
    await session.refresh(video)

    await storage.put_object(
        minio_client,
        settings.minio_bucket,
        storage_key,
        PLACEHOLDER_VIDEO,
        content_type="video/mp4",
    )
    await storage.put_object(
        minio_client,
        settings.minio_bucket,
        thumbnail_key,
        PLACEHOLDER_PREVIEW,
        content_type="image/png",
    )
    return video


async def seed() -> None:
    """Populate the demo dataset idempotently."""

    init_engine()
    session_factory = get_session_factory()
    minio_client = storage.create_minio_client()
    await storage.ensure_bucket(minio_client, settings.minio_bucket)

    try:
        async with session_factory() as session:
            users = [await ensure_user(session, data) for data in DEMO_USERS]
            admin, moderator, regular = users

            videos = []
            for index, (slug, title, description) in enumerate(DEMO_VIDEOS, start=1):
                videos.append(
                    await ensure_video(
                        session,
                        admin,
                        index,
                        slug,
                        title,
                        description,
                        minio_client,
                    )
                )

            comment_count = await session.scalar(select(func.count(Comment.id)))
            if not comment_count:
                session.add_all(
                    [
                        Comment(
                            video_id=videos[0].id,
                            author_id=regular.id,
                            content="Отличная демо-лента!",
                        ),
                        Comment(
                            video_id=videos[1].id,
                            author_id=moderator.id,
                            content="Presigned URL — удобно и безопасно.",
                        ),
                        Comment(
                            video_id=videos[2].id,
                            author_id=admin.id,
                            content="FastAPI действительно быстрый.",
                        ),
                    ]
                )
                await session.commit()

            like_count = await session.scalar(select(func.count(Like.id)))
            if not like_count:
                for video in videos:
                    for user in users:
                        session.add(Like(user_id=user.id, video_id=video.id))
                await session.commit()

            print("Demo data ready:")
            print(f"  videos: {len(videos)}")
            print("  users:")
            for data in DEMO_USERS:
                print(f"    {data['email']} / {data['password']} ({data['role'].value})")
            print(f"  bucket: {settings.minio_bucket}")
            print("  open: http://localhost:8000/")
    finally:
        close = getattr(minio_client, "close", None)
        if callable(close):
            close()
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(seed())
