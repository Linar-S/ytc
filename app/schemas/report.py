"""Report request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator

from app.models.enums import ReportReason
from app.schemas.common import ORMModel


class ReportCreate(BaseModel):
    """Payload for reporting a video or a comment."""

    video_id: UUID | None = None
    comment_id: UUID | None = None
    reason: ReportReason

    @model_validator(mode="after")
    def require_target(self) -> "ReportCreate":
        """Require exactly one moderation target."""

        if (self.video_id is None) == (self.comment_id is None):
            raise ValueError("exactly one of video_id or comment_id is required")
        return self


class ReportOut(ORMModel):
    """Public representation of a moderation report."""

    id: UUID
    reporter_id: UUID
    video_id: UUID | None
    comment_id: UUID | None
    reason: str
    status: str
    created_at: datetime
    updated_at: datetime
