"""Failure report model."""

from pydantic import Field

from ai_crawler.core.models.base import DomainModel


class FailureReport(DomainModel):
    """Explicit failure model used instead of nullable error returns."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool = False
    evidence_refs: tuple[str, ...] = ()
