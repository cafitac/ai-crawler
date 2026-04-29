"""Crawler recipe model."""

from typing import Literal

from pydantic import Field, field_validator

from ai_crawler.core.models.base import DomainModel
from ai_crawler.core.models.request import RequestSpec


class PaginationSpec(DomainModel):
    """Declarative pagination behavior."""

    strategy: str = "none"
    query_param: str = ""
    start: int = Field(default=1, ge=0)
    max_pages: int = Field(default=1, ge=1)


class ExtractSpec(DomainModel):
    """Declarative extraction target."""

    item_path: str = ""
    fields: dict[str, str] = Field(default_factory=dict)


class ValidationSpec(DomainModel):
    """Recipe validation constraints."""

    min_items: int = Field(default=0, ge=0)


class ExecutionSpec(DomainModel):
    """Deterministic crawler execution options."""

    concurrency: int = Field(default=1, ge=1)
    delay_ms: int = Field(default=0, ge=0)
    max_items: int | None = Field(default=None, ge=0)
    max_seconds: int | None = Field(default=None, gt=0)
    retry_attempts: int = Field(default=0, ge=0)
    retry_backoff_ms: int = Field(default=0, ge=0)
    retry_statuses: tuple[int, ...] = (500, 502, 503, 504)
    checkpoint_path: str = ""

    @field_validator("retry_statuses")
    @classmethod
    def validate_retry_statuses(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(set(value)) != len(value):
            msg = "retry_statuses must not contain duplicates"
            raise ValueError(msg)
        invalid = tuple(status for status in value if not 200 <= status <= 599)
        if invalid:
            msg = f"retry_statuses must contain valid HTTP status codes: {invalid}"
            raise ValueError(msg)
        return value

    @field_validator("checkpoint_path")
    @classmethod
    def validate_checkpoint_path(cls, value: str) -> str:
        if value and not value.strip():
            msg = "checkpoint_path must be empty or a non-blank path"
            raise ValueError(msg)
        return value


RunnerStopReason = Literal[
    "completed",
    "non_success_status",
    "empty_page",
    "max_items_reached",
    "max_seconds_reached",
    "challenge_detected",
    "retry_exhausted",
]


DEFAULT_PAGINATION_SPEC = PaginationSpec()
DEFAULT_EXTRACT_SPEC = ExtractSpec()
DEFAULT_VALIDATION_SPEC = ValidationSpec()
DEFAULT_EXECUTION_SPEC = ExecutionSpec()


class Recipe(DomainModel):
    """Declarative crawler recipe."""

    name: str = Field(min_length=1)
    start_url: str = Field(min_length=1)
    requests: tuple[RequestSpec, ...] = Field(min_length=1)
    pagination: PaginationSpec = DEFAULT_PAGINATION_SPEC
    extract: ExtractSpec = DEFAULT_EXTRACT_SPEC
    validation: ValidationSpec = DEFAULT_VALIDATION_SPEC
    execution: ExecutionSpec = DEFAULT_EXECUTION_SPEC

    @field_validator("requests", mode="before")
    @classmethod
    def normalize_legacy_request_strings(cls, value: object) -> object:
        if not isinstance(value, tuple | list):
            return value
        return tuple(_normalize_request_item(item) for item in value)


def _normalize_request_item(item: object) -> object:
    if not isinstance(item, str):
        return item
    method, separator, url = item.partition(" ")
    if not separator:
        return item
    return {"method": method, "url": url}
