"""Video request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.enums import VideoStatus, Visibility
from app.schemas.common import ORMModel


class VideoCreate(BaseModel):
    """Payload for creating a video record before upload."""

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    visibility: Visibility = Visibility.PUBLIC


class VideoUpdate(BaseModel):
    """Fields the owner may update on a video."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    visibility: Visibility | None = None


class VideoInitUploadRequest(BaseModel):
    """Metadata required to reserve a direct-to-MinIO upload."""

    model_config = ConfigDict(populate_by_name=True)

    filename: str = Field(
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("filename", "file_name", "name"),
    )
    content_type: str = Field(
        min_length=1,
        max_length=100,
        validation_alias=AliasChoices("content_type", "mime_type"),
    )
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    visibility: Visibility = Visibility.PUBLIC
    file_size: int | None = Field(
        default=None,
        ge=1,
        validation_alias=AliasChoices("file_size", "size", "size_bytes", "content_length"),
    )


class VideoInitUploadResponse(BaseModel):
    """Presigned upload instructions returned by init-upload."""

    video_id: UUID
    upload_url: str
    object_key: str
    expires_in: int


class VideoOut(ORMModel):
    """Public representation of a video."""

    id: UUID
    owner_id: UUID
    title: str
    description: str | None
    status: VideoStatus
    visibility: Visibility
    storage_key: str | None
    thumbnail_key: str | None
    duration_seconds: int | None
    views_count: int
    created_at: datetime
    updated_at: datetime
