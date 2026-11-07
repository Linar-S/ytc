"""Domain enums shared by ORM models and Pydantic schemas."""

from enum import StrEnum


class UserRole(StrEnum):
    """Roles available to a registered user."""

    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"


class VideoStatus(StrEnum):
    """Lifecycle of an uploaded video."""

    UPLOADING = "uploading"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    HIDDEN = "hidden"


class Visibility(StrEnum):
    """Who is allowed to watch a video."""

    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"
