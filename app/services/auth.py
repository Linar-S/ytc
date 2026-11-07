"""Authentication service: password hashing and JWT lifecycle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import RefreshToken, User, UserRole
from app.repositories import refresh_tokens as refresh_token_repo
from app.repositories import users as user_repo
from app.schemas.user import UserCreate

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthError(Exception):
    """Base class for authentication failures."""


class UserAlreadyExistsError(AuthError):
    """Raised when a unique email or username is already in use."""


class InvalidCredentialsError(AuthError):
    """Raised when login credentials do not match an active user."""


class InvalidTokenError(AuthError):
    """Raised when a JWT is malformed, expired or revoked."""


class AuthConfigurationError(AuthError):
    """Raised when required auth settings are missing."""


@dataclass(frozen=True)
class IssuedTokens:
    """Token pair plus access-token lifetime for API responses."""

    access_token: str
    refresh_token: str
    expires_in: int


def _signing_key() -> str:
    """Return the configured JWT signing key."""

    if not settings.jwt_secret_key:
        raise AuthConfigurationError("JWT secret key is not configured")
    return settings.jwt_secret_key


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""

    return pwd_context.hash(password)


get_password_hash = hash_password


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""

    try:
        return pwd_context.verify(password, password_hash)
    except (TypeError, ValueError):
        return False


def _create_token(
    user_id: uuid.UUID,
    token_type: str,
    lifetime: timedelta,
) -> tuple[str, str, datetime]:
    """Create a signed JWT and return its value, jti and expiry."""

    now = datetime.now(UTC)
    expires_at = now + lifetime
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": expires_at,
    }
    token = jwt.encode(payload, _signing_key(), algorithm=settings.jwt_algorithm)
    return token, jti, expires_at


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a short-lived access token."""

    token, _jti, _expires_at = _create_token(
        user_id,
        ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )
    return token


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived refresh token (persistence is handled separately)."""

    token, _jti, _expires_at = _create_token(
        user_id,
        REFRESH_TOKEN_TYPE,
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    return token


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """Decode and validate a JWT, ensuring its type and required claims."""

    try:
        payload = jwt.decode(
            token,
            _signing_key(),
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise InvalidTokenError("Invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise InvalidTokenError("Invalid token type")
    if not payload.get("sub") or not payload.get("jti"):
        raise InvalidTokenError("Token is missing required claims")
    return payload


def _user_id_from_payload(payload: dict[str, Any]) -> uuid.UUID:
    """Parse the JWT subject into a UUID."""

    try:
        return uuid.UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid token subject") from exc


def _utc(value: datetime) -> datetime:
    """Normalize SQLite's naive datetimes to UTC-aware datetimes."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


async def get_user_from_access_token(session: AsyncSession, token: str) -> User:
    """Resolve an active user from an access JWT."""

    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    user = await user_repo.get_by_id(session, _user_id_from_payload(payload))
    if user is None or not user.is_active:
        raise InvalidTokenError("User is not active")
    return user


async def register_user(session: AsyncSession, payload: UserCreate) -> User:
    """Register a user; the very first registered account becomes admin."""

    email = payload.email.strip().lower()
    username = payload.username.strip()

    if await user_repo.get_by_email(session, email) is not None:
        raise UserAlreadyExistsError("Email already registered")
    if await user_repo.get_by_username(session, username) is not None:
        raise UserAlreadyExistsError("Username already taken")

    is_first_user = await user_repo.count_users(session) == 0
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN if is_first_user else UserRole.USER,
        is_active=True,
    )
    user_repo.add_user(session, user)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise UserAlreadyExistsError("Email or username already registered") from exc

    await session.refresh(user)
    return user


async def authenticate_user(
    session: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Validate login credentials and return an active user."""

    user = await user_repo.get_by_email(session, email.strip().lower())
    if user is None or not user.is_active or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email or password")
    return user


async def issue_token_pair(session: AsyncSession, user: User) -> IssuedTokens:
    """Issue and persist a new access/refresh token pair."""

    access_token = create_access_token(user.id)
    refresh_token, jti, expires_at = _create_token(
        user.id,
        REFRESH_TOKEN_TYPE,
        timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    await refresh_token_repo.add_refresh_token(
        session,
        RefreshToken(user_id=user.id, jti=jti, expires_at=expires_at),
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise InvalidTokenError("Could not persist refresh token") from exc

    return IssuedTokens(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def login(
    session: AsyncSession,
    email: str,
    password: str,
) -> tuple[User, IssuedTokens]:
    """Authenticate a user and issue a fresh token pair."""

    user = await authenticate_user(session, email, password)
    tokens = await issue_token_pair(session, user)
    return user, tokens


async def rotate_refresh_token(
    session: AsyncSession,
    refresh_token: str,
) -> tuple[User, IssuedTokens]:
    """Revoke an old refresh token and issue a replacement pair."""

    payload = decode_token(refresh_token, REFRESH_TOKEN_TYPE)
    jti = str(payload["jti"])
    record = await refresh_token_repo.get_active_by_jti(session, jti)
    if record is None:
        raise InvalidTokenError("Refresh token revoked or unknown")
    if _utc(record.expires_at) <= datetime.now(UTC):
        raise InvalidTokenError("Refresh token expired")

    user = await user_repo.get_by_id(session, _user_id_from_payload(payload))
    if user is None or not user.is_active:
        raise InvalidTokenError("User is not active")
    if record.user_id != user.id:
        raise InvalidTokenError("Refresh token does not belong to user")

    refresh_token_repo.revoke_token(record, datetime.now(UTC))
    tokens = await issue_token_pair(session, user)
    return user, tokens


async def logout(
    session: AsyncSession,
    user: User,
    refresh_token: str | None = None,
) -> None:
    """Revoke the supplied refresh token, or all active tokens for the user."""

    if refresh_token:
        try:
            payload = decode_token(refresh_token, REFRESH_TOKEN_TYPE)
        except InvalidTokenError:
            await refresh_token_repo.revoke_all_for_user(session, user.id, datetime.now(UTC))
            await session.commit()
            return

        if _user_id_from_payload(payload) == user.id:
            record = await refresh_token_repo.get_active_by_jti(session, str(payload["jti"]))
            if record is not None:
                refresh_token_repo.revoke_token(record, datetime.now(UTC))
    else:
        await refresh_token_repo.revoke_all_for_user(session, user.id, datetime.now(UTC))

    await session.commit()


verify_token = decode_token
