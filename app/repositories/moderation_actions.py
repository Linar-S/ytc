"""Database queries for moderation audit actions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModerationAction


def add_action(session: AsyncSession, action: ModerationAction) -> ModerationAction:
    """Stage a moderation action row."""

    session.add(action)
    return action
