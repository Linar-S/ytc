"""Reusable FastAPI authentication dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserRole
from app.services import auth as auth_service

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    """Build a consistent 401 response with a Bearer challenge."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the current user from a valid access token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    try:
        return await auth_service.get_user_from_access_token(session, credentials.credentials)
    except auth_service.InvalidTokenError as exc:
        raise _unauthorized() from exc
    except auth_service.AuthConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured",
        ) from exc


def require_role(*roles: UserRole | str) -> Callable[..., object]:
    """Return a dependency that allows only the supplied roles."""

    allowed_roles = {UserRole(role) for role in roles}

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker


async def get_optional_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Return the current user when a valid token is supplied, otherwise None."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        return await auth_service.get_user_from_access_token(session, credentials.credentials)
    except (auth_service.InvalidTokenError, auth_service.AuthConfigurationError):
        return None
