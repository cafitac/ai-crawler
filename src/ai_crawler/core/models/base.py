"""Shared Pydantic base model configuration."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base class for immutable ai-crawler domain models."""

    model_config = ConfigDict(frozen=True, extra="forbid")
