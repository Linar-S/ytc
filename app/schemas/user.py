"""User request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Perform a small dependency-free sanity check for an email address."""

        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain:
            raise ValueError("invalid email address")
        return value.lower()


class UserUpdate(BaseModel):
    """Fields a user may change on their own profile."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserOut(ORMModel):
    """Public representation of a user."""

    id: UUID
    email: str
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
