"""Authentication request and response schemas."""

from pydantic import AliasChoices, BaseModel, Field


class LoginRequest(BaseModel):
    """Email/password credentials."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Refresh-token payload used by refresh and logout."""

    refresh_token: str = Field(
        min_length=1,
        validation_alias=AliasChoices("refresh_token", "token"),
    )


class LogoutRequest(BaseModel):
    """Optional refresh token to revoke on logout.

    When omitted, all active refresh tokens of the authenticated user are
    revoked.
    """

    refresh_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("refresh_token", "token"),
    )


class TokenResponse(BaseModel):
    """Access/refresh token pair returned after login or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class MessageResponse(BaseModel):
    """Simple operation result."""

    detail: str


# Compatibility aliases for callers that use the pair terminology.
TokenPair = TokenResponse
RefreshRequest = RefreshTokenRequest
