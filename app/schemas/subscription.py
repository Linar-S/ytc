"""Subscription request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel


class SubscriptionCreate(BaseModel):
    """Payload for subscribing to a channel; subscriber comes from auth."""

    channel_id: UUID


class SubscriptionOut(ORMModel):
    """Public representation of a subscription."""

    id: UUID
    subscriber_id: UUID
    channel_id: UUID
    created_at: datetime
