"""Video ORM model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.database import Base
from app.models.enums import VideoStatus, Visibility
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.like import Like
    from app.models.user import User


def _enum_values(enum_cls: type) -> list[str]:
    return [item.value for item in enum_cls]


class Video(TimestampMixin, Base):
    """A video owned by a user and stored in object storage."""

    __tablename__ = "videos"
    __table_args__ = (Index("ix_videos_owner_id_created_at", "owner_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status", values_callable=_enum_values),
        nullable=False,
        default=VideoStatus.UPLOADING,
        server_default=VideoStatus.UPLOADING.value,
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, name="visibility", values_callable=_enum_values),
        nullable=False,
        default=Visibility.PUBLIC,
        server_default=Visibility.PUBLIC.value,
    )
    storage_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )

    duration = synonym("duration_seconds")

    owner: Mapped[User] = relationship(back_populates="videos")
    comments: Mapped[list[Comment]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    likes: Mapped[list[Like]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
