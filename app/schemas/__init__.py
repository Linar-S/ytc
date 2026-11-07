"""Pydantic request and response schemas."""

from app.models.enums import UserRole, VideoStatus, Visibility
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RefreshTokenRequest,
    TokenPair,
    TokenResponse,
)
from app.schemas.comment import (
    CommentCreate,
    CommentOut,
    CommentUpdate,
    PaginatedComments,
)
from app.schemas.like import LikeCreate, LikeOut
from app.schemas.report import ReportCreate, ReportOut
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.schemas.video import (
    LikeStatusResponse,
    PaginatedVideos,
    VideoCreate,
    VideoDetailOut,
    VideoFeedItem,
    VideoInitUploadRequest,
    VideoInitUploadResponse,
    VideoOut,
    VideoUpdate,
)

__all__ = [
    "CommentCreate",
    "CommentOut",
    "CommentUpdate",
    "LikeCreate",
    "LikeOut",
    "LikeStatusResponse",
    "LoginRequest",
    "LogoutRequest",
    "MessageResponse",
    "PaginatedComments",
    "PaginatedVideos",
    "RefreshRequest",
    "RefreshTokenRequest",
    "ReportCreate",
    "ReportOut",
    "SubscriptionCreate",
    "SubscriptionOut",
    "TokenPair",
    "TokenResponse",
    "UserCreate",
    "UserOut",
    "UserRole",
    "UserUpdate",
    "VideoCreate",
    "VideoDetailOut",
    "VideoFeedItem",
    "VideoInitUploadRequest",
    "VideoInitUploadResponse",
    "VideoOut",
    "VideoStatus",
    "VideoUpdate",
    "Visibility",
]
