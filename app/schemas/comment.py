"""Comment request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field

from app.schemas.common import ORMModel


class CommentCreate(BaseModel):
    """Payload for commenting on a video."""

    content: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("content", "text"),
    )

    @property
    def text(self) -> str:
        """Compatibility alias for clients that call the field ``text``."""

        return self.content


class CommentUpdate(BaseModel):
    """Payload for editing an existing comment."""

    content: str = Field(
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("content", "text"),
    )

    @property
    def text(self) -> str:
        """Compatibility alias for clients that call the field ``text``."""

        return self.content


class CommentOut(ORMModel):
    """Public representation of a comment."""

    id: UUID
    video_id: UUID
    author_id: UUID
    content: str = Field(validation_alias=AliasChoices("content", "text"))
    created_at: datetime
    updated_at: datetime

    @property
    def text(self) -> str:
        """Compatibility alias for clients that call the field ``text``."""

        return self.content
