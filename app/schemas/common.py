"""Shared Pydantic schema configuration."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base response model that can be populated from SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)
