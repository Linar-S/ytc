"""Database queries for users."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    """Return a user with the normalized email address, if present."""

    return await session.scalar(select(User).where(User.email == email.lower()))


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    """Return a user with the given username, if present."""

    return await session.scalar(select(User).where(User.username == username))


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Return a user by primary key."""

    return await session.get(User, user_id)


async def count_users(session: AsyncSession) -> int:
    """Return the total number of registered users."""

    value = await session.scalar(select(func.count(User.id)))
    return int(value or 0)


def add_user(session: AsyncSession, user: User) -> User:
    """Stage a new user for insertion."""

    session.add(user)
    return user
