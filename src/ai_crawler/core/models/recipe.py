"""Crawler recipe model."""

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
