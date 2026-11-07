"""ORM model tests against an in-memory async SQLite database."""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import (
    Comment,
    Like,
    Report,
    Subscription,
    User,
    UserRole,
    Video,
    VideoStatus,
    Visibility,
)
from app.schemas import CommentOut, UserOut, VideoOut


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Create an isolated in-memory database with FK enforcement enabled."""

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
    async with session_factory() as db_session:
        yield db_session

    await engine.dispose()


async def _create_user(session: AsyncSession, suffix: str = "") -> User:
    user = User(
        email=f"alice{suffix}@example.com",
        username=f"alice{suffix}",
        hashed_password="$2b$12$not-a-real-hash",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def test_create_user_video_comment(session: AsyncSession) -> None:
    """User, video and comment round-trip through the async ORM."""

    user = await _create_user(session)
    assert user.id is not None
    assert user.role is UserRole.USER
    assert user.is_active is True
    assert user.created_at is not None

    video = Video(
        owner_id=user.id,
        title="First video",
        description="A test video",
        status=VideoStatus.PROCESSING,
        visibility=Visibility.UNLISTED,
        storage_key="videos/first.mp4",
    )
    session.add(video)
    await session.commit()
    await session.refresh(video)

    comment = Comment(video_id=video.id, author_id=user.id, content="Nice video!")
    session.add(comment)
    await session.commit()
    await session.refresh(comment)

    assert video.owner_id == user.id
    assert video.status is VideoStatus.PROCESSING
    assert video.visibility is Visibility.UNLISTED
    assert comment.video_id == video.id
    assert comment.author_id == user.id
    assert comment.text == "Nice video!"

    user_schema = UserOut.model_validate(user)
    video_schema = VideoOut.model_validate(video)
    comment_schema = CommentOut.model_validate(comment)
    assert user_schema.role is UserRole.USER
    assert video_schema.owner_id == user.id
    assert comment_schema.content == "Nice video!"


async def test_video_delete_cascades_comments_likes_and_reports(
    session: AsyncSession,
) -> None:
    """Deleting a video removes all child rows via the database cascade."""

    user = await _create_user(session)
    video = Video(owner_id=user.id, title="Cascade me", status=VideoStatus.READY)
    session.add(video)
    await session.commit()
    await session.refresh(video)

    session.add_all(
        [
            Comment(video_id=video.id, author_id=user.id, content="first"),
            Comment(video_id=video.id, author_id=user.id, content="second"),
            Like(user_id=user.id, video_id=video.id),
            Report(reporter_id=user.id, video_id=video.id, reason="spam"),
        ]
    )
    await session.commit()

    await session.delete(video)
    await session.commit()

    assert await session.scalar(select(func.count()).select_from(Comment)) == 0
    assert await session.scalar(select(func.count()).select_from(Like)) == 0
    assert await session.scalar(select(func.count()).select_from(Report)) == 0
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_user_delete_cascades_videos_and_subscriptions(
    session: AsyncSession,
) -> None:
    """Deleting a user removes their videos and subscription edges."""

    author = await _create_user(session)
    subscriber = await _create_user(session, "2")
    video = Video(owner_id=author.id, title="Owned video")
    session.add(video)
    session.add(Subscription(subscriber_id=subscriber.id, channel_id=author.id))
    await session.commit()

    await session.delete(author)
    await session.commit()

    assert await session.scalar(select(func.count()).select_from(Video)) == 0
    assert await session.scalar(select(func.count()).select_from(Subscription)) == 0
    assert await session.scalar(select(func.count()).select_from(User)) == 1
