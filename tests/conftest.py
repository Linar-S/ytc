"""Shared pytest fixtures."""

import os
from collections.abc import AsyncIterator

# Configure a deterministic development signing key before app settings load.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-32chars")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Provide a client and run the application lifespan around each test."""

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
