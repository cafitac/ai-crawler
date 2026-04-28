"""HTTP request and fetch option models."""

from pydantic import Field, field_validator, model_validator

from ai_crawler.core.models.base import DomainModel

_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class RequestSpec(DomainModel):
    """Normalized HTTP request specification."""

    id: str = ""
    method: str = Field(min_length=1)
    url: str = Field(min_length=1)
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    cookies: dict[str, str] = Field(default_factory=dict)
    body: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_query_alias(cls, value: object) -> object:
        if isinstance(value, dict) and "params" in value and "query" not in value:
            normalized = dict(value)
            normalized["query"] = normalized.pop("params")
            return normalized
        return value

    @property
    def params(self) -> dict[str, str]:
        """Alias used by HTTP clients for query parameters."""
        return self.query

    @field_validator("method")
    @classmethod
    def normalize_method(cls, value: str) -> str:
        method = value.upper()
        if method not in _ALLOWED_METHODS:
            msg = f"Unsupported HTTP method: {value}"
            raise ValueError(msg)
        return method


class FetchOptions(DomainModel):
    """Options controlling a single HTTP fetch."""

    timeout_s: float = Field(default=30.0, gt=0)
    retries: int = Field(default=0, ge=0)
    impersonate: str = ""
    proxy_url: str = ""
