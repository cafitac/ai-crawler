"""Network trace event model."""

from pydantic import Field, field_validator

from ai_crawler.core.models.base import DomainModel


class NetworkEvent(DomainModel):
    """Single normalized browser/network event."""

    method: str = Field(min_length=1)
    url: str = Field(min_length=1)
    status_code: int = Field(ge=100, le=599)
    resource_type: str = Field(min_length=1)

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        return value.upper()
