"""Pydantic request and response schemas."""

from app.models.enums import ReportReason, UserRole, VideoStatus, Visibility
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RefreshTokenRequest,
    TokenPair,
    TokenResponse,
)
from app.schemas.channel import ChannelOut, SubscribeResponse
from app.schemas.comment import (
    CommentCreate,
    CommentOut,
    CommentUpdate,
    PaginatedComments,
)
from app.schemas.like import LikeCreate, LikeOut
from app.schemas.moderation import (
    ModerationActionResponse,
    ModerationQueueItem,
    ModerationQueueResponse,
    VideoReportCreate,
    VideoReportResponse,
)
from app.schemas.report import ReportCreate, ReportOut
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.schemas.video import (
    LikeStatusResponse,
    PaginatedVideos,
    VideoAccessRequest,
    VideoAccessResponse,
    VideoCreate,
    VideoDetailOut,
    VideoFeedItem,
    VideoInitUploadRequest,
    VideoInitUploadResponse,
    VideoOut,
    VideoUpdate,
)

__all__ = [
    "ChannelOut",
    "CommentCreate",
    "CommentOut",
    "CommentUpdate",
    "LikeCreate",
    "LikeOut",
    "LikeStatusResponse",
    "LoginRequest",
    "LogoutRequest",
    "MessageResponse",
    "ModerationActionResponse",
    "ModerationQueueItem",
    "ModerationQueueResponse",
    "PaginatedComments",
    "PaginatedVideos",
    "RefreshRequest",
    "RefreshTokenRequest",
    "ReportCreate",
    "ReportOut",
    "ReportReason",
    "SubscribeResponse",
    "SubscriptionCreate",
    "SubscriptionOut",
    "TokenPair",
    "TokenResponse",
    "UserCreate",
    "UserOut",
    "UserRole",
    "UserUpdate",
    "VideoAccessRequest",
    "VideoAccessResponse",
    "VideoCreate",
    "VideoDetailOut",
    "VideoFeedItem",
    "VideoInitUploadRequest",
    "VideoInitUploadResponse",
    "VideoOut",
    "VideoReportCreate",
    "VideoReportResponse",
    "VideoStatus",
    "VideoUpdate",
    "Visibility",
]
