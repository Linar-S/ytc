"""Business logic for channels and subscriptions."""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import subscriptions as subscription_repo
from app.repositories import users as user_repo
from app.repositories import videos as video_repo
from app.schemas.channel import ChannelOut
from app.services import videos as video_service


class ChannelNotFoundError(Exception):
    """Raised when a channel user does not exist."""


class SelfSubscriptionError(Exception):
    """Raised when a user tries to subscribe to their own channel."""


async def get_channel(
    session: AsyncSession,
    channel_id: uuid.UUID,
    viewer: User | None,
    minio_client,
    bucket: str,
) -> ChannelOut:
    """Return channel profile and videos visible to the viewer."""

    channel = await user_repo.get_by_id(session, channel_id)
    if channel is None:
        raise ChannelNotFoundError("Channel not found")

    videos = await video_repo.list_channel_videos(
        session,
        channel.id,
        viewer.id if viewer is not None else None,
    )
    items = await video_service.build_feed_items(session, videos, minio_client, bucket)
    subscriber_count = await subscription_repo.count_for_channel(session, channel.id)
    is_subscribed = False
    if viewer is not None:
        is_subscribed = await subscription_repo.is_subscribed(session, viewer.id, channel.id)

    return ChannelOut(
        id=channel.id,
        username=channel.username,
        video_count=len(items),
        subscriber_count=subscriber_count,
        is_subscribed=is_subscribed,
        videos=items,
    )


async def subscribe(
    session: AsyncSession,
    subscriber: User,
    channel_id: uuid.UUID,
) -> tuple[bool, int]:
    """Idempotently subscribe to a channel."""

    channel = await user_repo.get_by_id(session, channel_id)
    if channel is None:
        raise ChannelNotFoundError("Channel not found")
    if channel.id == subscriber.id:
        raise SelfSubscriptionError("Cannot subscribe to yourself")

    existing = await subscription_repo.get_subscription(session, subscriber.id, channel.id)
    if existing is None:
        subscription_repo.add_subscription(session, subscriber.id, channel.id)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

    count = await subscription_repo.count_for_channel(session, channel.id)
    return True, count


async def unsubscribe(
    session: AsyncSession,
    subscriber: User,
    channel_id: uuid.UUID,
) -> tuple[bool, int]:
    """Idempotently remove a channel subscription."""

    channel = await user_repo.get_by_id(session, channel_id)
    if channel is None:
        raise ChannelNotFoundError("Channel not found")
    if channel.id == subscriber.id:
        raise SelfSubscriptionError("Cannot unsubscribe from yourself")

    await subscription_repo.delete_subscription(session, subscriber.id, channel.id)
    await session.commit()
    count = await subscription_repo.count_for_channel(session, channel.id)
    return False, count
