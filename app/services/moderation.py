"""Reports, auto-hide and moderator actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ModerationAction,
    Report,
    ReportReason,
    User,
    Video,
    VideoStatus,
)
from app.repositories import moderation_actions as action_repo
from app.repositories import reports as report_repo
from app.repositories import videos as video_repo
from app.schemas.moderation import ModerationQueueItem
from app.schemas.video import VideoOut
from app.services import videos as video_service

RATE_LIMIT_PER_HOUR = 5
AUTO_HIDE_REPORTS = 5


class RateLimitExceededError(Exception):
    """Raised when a user exceeds the hourly report limit."""


@dataclass(frozen=True)
class ReportResult:
    """Created report plus moderation counters."""

    report: Report
    report_count: int
    auto_hidden: bool


async def report_video(
    session: AsyncSession,
    reporter: User,
    video_id: uuid.UUID,
    reason: ReportReason,
) -> ReportResult:
    """Submit a report, enforce rate limits and auto-hide abusive videos."""

    video = await video_repo.get_by_id(session, video_id)
    if video is None:
        raise video_service.VideoNotFoundError("Video not found")

    since = datetime.now(UTC) - timedelta(hours=1)
    recent = await report_repo.count_reports_since(session, reporter.id, since)
    if recent >= RATE_LIMIT_PER_HOUR:
        raise RateLimitExceededError("Report rate limit exceeded")

    report = Report(
        reporter_id=reporter.id,
        video_id=video.id,
        reason=reason.value,
    )
    report_repo.add_report(session, report)
    await session.commit()
    await session.refresh(report)

    distinct_reporters = await report_repo.count_distinct_reporters(session, video.id)
    auto_hidden = False
    if distinct_reporters >= AUTO_HIDE_REPORTS and video.status is not VideoStatus.HIDDEN:
        video.status = VideoStatus.HIDDEN
        await session.commit()
        auto_hidden = True

    report_count = await report_repo.count_for_video(session, video.id)
    return ReportResult(
        report=report,
        report_count=report_count,
        auto_hidden=auto_hidden,
    )


async def list_moderation_queue(session: AsyncSession) -> list[ModerationQueueItem]:
    """Return reported videos ordered by report count."""

    rows = await report_repo.list_moderation_queue(session)
    items: list[ModerationQueueItem] = []
    for video, report_count in rows:
        base = VideoOut.model_validate(video).model_dump()
        items.append(
            ModerationQueueItem(
                **base,
                owner_username=video.owner.username if video.owner else None,
                report_count=report_count,
            )
        )
    return items


async def _set_hidden(
    session: AsyncSession,
    moderator: User,
    video_id: uuid.UUID,
    *,
    hidden: bool,
) -> Video:
    """Apply a hide/unhide action and persist an audit record."""

    video = await video_repo.get_by_id(session, video_id)
    if video is None:
        raise video_service.VideoNotFoundError("Video not found")

    video.status = VideoStatus.HIDDEN if hidden else VideoStatus.READY
    action_repo.add_action(
        session,
        ModerationAction(
            moderator_id=moderator.id,
            video_id=video.id,
            action="hide" if hidden else "unhide",
        ),
    )
    await session.commit()
    await session.refresh(video)
    return video


async def hide_video(session: AsyncSession, moderator: User, video_id: uuid.UUID) -> Video:
    """Hide a video from public surfaces and audit the action."""

    return await _set_hidden(session, moderator, video_id, hidden=True)


async def unhide_video(session: AsyncSession, moderator: User, video_id: uuid.UUID) -> Video:
    """Restore a hidden video and audit the action."""

    return await _set_hidden(session, moderator, video_id, hidden=False)
