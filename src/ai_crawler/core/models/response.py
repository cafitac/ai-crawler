"""HTTP response domain model."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel


class FetchResponse(DomainModel):
    """Normalized HTTP response captured by an adapter."""

    url: str = Field(min_length=1)
    status_code: int = Field(ge=100, le=599)
    headers: dict[str, str]
    body_text: str
    elapsed_ms: int = Field(ge=0)
