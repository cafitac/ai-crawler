"""Endpoint candidate domain model."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel


class EndpointCandidate(DomainModel):
    """Scored candidate network endpoint inferred from trace events."""

    url: str = Field(min_length=1)
    method: str = Field(min_length=1)
    status_code: int = Field(ge=100, le=599)
    resource_type: str = Field(min_length=1)
    score: int = Field(ge=0)
    reasons: tuple[str, ...] = ()
