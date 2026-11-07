"""Comment ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.video import Video


class Comment(TimestampMixin, Base):
    """A comment left by a user under a video."""

    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_video_id_created_at", "video_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ``text`` is kept as an ORM-level alias for code that uses the field
    # name from the API request schema.
    text = synonym("content")
    user_id = synonym("author_id")

    video: Mapped[Video] = relationship(back_populates="comments")
    author: Mapped[User] = relationship(back_populates="comments")
