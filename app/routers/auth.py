"""Authentication and registration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User, UserRole
from app.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _token_response(tokens: auth_service.IssuedTokens) -> TokenResponse:
    """Convert the service token bundle into the API response schema."""

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Register a user; the first account receives the admin role."""

    try:
        return await auth_service.register_user(session, payload)
    except auth_service.UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Validate credentials and return an access/refresh token pair."""

    try:
        _user, tokens = await auth_service.login(session, payload.email, payload.password)
    except auth_service.InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except auth_service.AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured",
        ) from exc

    return _token_response(tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshTokenRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate a refresh token and return a new token pair."""

    if not payload.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        _user, tokens = await auth_service.rotate_refresh_token(session, payload.refresh_token)
    except auth_service.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except auth_service.AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured",
        ) from exc

    return _token_response(tokens)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    payload: Annotated[LogoutRequest | None, Body()] = None,
) -> MessageResponse:
    """Revoke one refresh token, or all sessions when no token is supplied."""

    await auth_service.logout(
        session,
        current_user,
        payload.refresh_token if payload else None,
    )
    return MessageResponse(detail="Logged out")


@router.get("/me", response_model=UserOut)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the authenticated user's profile."""

    return current_user


@router.get("/admin-only", response_model=MessageResponse)
async def admin_only(
    _current_user: Annotated[User, Depends(require_role(UserRole.ADMIN))],
) -> MessageResponse:
    """Role-protected demo endpoint used to verify RBAC."""

    return MessageResponse(detail="Admin access granted")
