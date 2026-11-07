"""Health endpoint tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_needs_no_auth(async_client: AsyncClient) -> None:
    """The liveness probe is public and returns the documented payload."""

    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
