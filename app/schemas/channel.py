"""Channel and subscription schemas."""

from uuid import UUID

from pydantic import BaseModel

from app.schemas.video import VideoFeedItem


class ChannelOut(BaseModel):
    """Public channel profile with visible videos."""

    id: UUID
    username: str
    video_count: int
    subscriber_count: int
    is_subscribed: bool
    videos: list[VideoFeedItem]


class SubscribeResponse(BaseModel):
    """Idempotent subscription result."""

    subscribed: bool
    subscriber_count: int
