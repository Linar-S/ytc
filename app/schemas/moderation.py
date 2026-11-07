"""Search and moderation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ReportReason, VideoStatus
from app.schemas.video import VideoOut


class VideoReportCreate(BaseModel):
    """Payload for reporting a video."""

    reason: ReportReason


class VideoReportResponse(BaseModel):
    """Result of submitting a video report."""

    id: UUID
    video_id: UUID
    reason: ReportReason
    report_count: int
    auto_hidden: bool


class ModerationQueueItem(VideoOut):
    """Reported video row shown in the moderation queue."""

    owner_username: str | None = None
    report_count: int
    created_at: datetime


class ModerationQueueResponse(BaseModel):
    """Reported videos sorted by report count."""

    items: list[ModerationQueueItem]
    total: int


class ModerationActionResponse(BaseModel):
    """Result of hiding or unhiding a video."""

    video_id: UUID
    status: VideoStatus
    action: str
