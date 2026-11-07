"""Like request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ORMModel


class LikeCreate(BaseModel):
    """Payload for liking a video; the user comes from auth."""

    video_id: UUID


class LikeOut(ORMModel):
    """Public representation of a like."""

    id: UUID
    user_id: UUID
    video_id: UUID
    created_at: datetime
