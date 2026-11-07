"""Database queries for reports and the moderation queue."""

import uuid
from datetime import datetime

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Report, Video


def add_report(session: AsyncSession, report: Report) -> Report:
    """Stage a new report row."""

    session.add(report)
    return report


async def count_reports_since(
    session: AsyncSession,
    reporter_id: uuid.UUID,
    since: datetime,
) -> int:
    """Count reports submitted by one user since a timestamp."""

    value = await session.scalar(
        select(func.count(Report.id)).where(
            Report.reporter_id == reporter_id,
            Report.created_at >= since,
        )
    )
    return int(value or 0)


async def count_for_video(session: AsyncSession, video_id: uuid.UUID) -> int:
    """Count all reports for a video."""

    value = await session.scalar(select(func.count(Report.id)).where(Report.video_id == video_id))
    return int(value or 0)


async def count_distinct_reporters(session: AsyncSession, video_id: uuid.UUID) -> int:
    """Count distinct users who reported a video."""

    value = await session.scalar(
        select(func.count(distinct(Report.reporter_id))).where(Report.video_id == video_id)
    )
    return int(value or 0)


async def list_moderation_queue(session: AsyncSession, limit: int = 100) -> list[tuple[Video, int]]:
    """Return reported videos sorted by report count descending."""

    rows = await session.execute(
        select(Video, func.count(Report.id).label("report_count"))
        .join(Report, Report.video_id == Video.id)
        .options(selectinload(Video.owner))
        .group_by(Video.id)
        .order_by(func.count(Report.id).desc(), Video.created_at.desc())
        .limit(limit)
    )
    return [(video, int(report_count)) for video, report_count in rows]
