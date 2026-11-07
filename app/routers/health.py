"""Unauthenticated liveness endpoint."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", status_code=200)
async def health_check() -> dict[str, str]:
    """Return a constant response when the process is alive."""

    return {"status": "ok"}
