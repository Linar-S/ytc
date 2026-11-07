"""Database queries for channel subscriptions."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription


async def get_subscription(
    session: AsyncSession, subscriber_id: uuid.UUID, channel_id: uuid.UUID
) -> Subscription | None:
    """Return a subscription row, if present."""

    return await session.scalar(
        select(Subscription).where(
            Subscription.subscriber_id == subscriber_id,
            Subscription.channel_id == channel_id,
        )
    )


def add_subscription(
    session: AsyncSession, subscriber_id: uuid.UUID, channel_id: uuid.UUID
) -> Subscription:
    """Stage a new subscription row."""

    subscription = Subscription(
        subscriber_id=subscriber_id,
        channel_id=channel_id,
    )
    session.add(subscription)
    return subscription


async def delete_subscription(
    session: AsyncSession, subscriber_id: uuid.UUID, channel_id: uuid.UUID
) -> None:
    """Delete a subscription if it exists (idempotent)."""

    await session.execute(
        delete(Subscription).where(
            Subscription.subscriber_id == subscriber_id,
            Subscription.channel_id == channel_id,
        )
    )


async def count_for_channel(session: AsyncSession, channel_id: uuid.UUID) -> int:
    """Count subscribers of a channel."""

    value = await session.scalar(
        select(func.count(Subscription.id)).where(Subscription.channel_id == channel_id)
    )
    return int(value or 0)


async def is_subscribed(
    session: AsyncSession, subscriber_id: uuid.UUID, channel_id: uuid.UUID
) -> bool:
    """Return whether a user follows a channel."""

    return await get_subscription(session, subscriber_id, channel_id) is not None
