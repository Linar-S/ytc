"""Channel profile and subscription endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, get_optional_current_user
from app.models import User
from app.schemas.channel import ChannelOut, SubscribeResponse
from app.services import channels as channel_service

router = APIRouter(prefix="/channels", tags=["channels"])


def _optional_minio_client(request: Request):
    return getattr(request.app.state, "minio_public_client", None) or getattr(
        request.app.state, "minio_client", None
    )


def _bucket(request: Request) -> str:
    return getattr(request.app.state, "minio_bucket", settings.minio_bucket)


@router.get("/{user_id}", response_model=ChannelOut)
async def get_channel(
    user_id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
) -> ChannelOut:
    """Return public channel info and videos visible to the viewer."""

    try:
        return await channel_service.get_channel(
            session,
            user_id,
            current_user,
            _optional_minio_client(request),
            _bucket(request),
        )
    except channel_service.ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/{user_id}/subscribe", response_model=SubscribeResponse)
async def subscribe(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscribeResponse:
    """Idempotently subscribe to a channel."""

    try:
        subscribed, subscriber_count = await channel_service.subscribe(
            session, current_user, user_id
        )
    except channel_service.ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except channel_service.SelfSubscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SubscribeResponse(
        subscribed=subscribed,
        subscriber_count=subscriber_count,
    )


@router.delete("/{user_id}/subscribe", response_model=SubscribeResponse)
async def unsubscribe(
    user_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SubscribeResponse:
    """Idempotently remove a channel subscription."""

    try:
        subscribed, subscriber_count = await channel_service.unsubscribe(
            session, current_user, user_id
        )
    except channel_service.ChannelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except channel_service.SelfSubscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return SubscribeResponse(
        subscribed=subscribed,
        subscriber_count=subscriber_count,
    )
