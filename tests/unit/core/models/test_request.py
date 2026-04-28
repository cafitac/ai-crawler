import pytest
from pydantic import ValidationError

from ai_crawler.core.models import FetchOptions, RequestSpec


def test_request_spec_normalizes_method_and_defaults_collections() -> None:
    request = RequestSpec(method="get", url="https://example.com/api/products")

    assert request.method == "GET"
    assert request.headers == {}
    assert request.params == {}
    assert request.cookies == {}
    assert request.body == ""


def test_request_spec_rejects_unsupported_method() -> None:
    with pytest.raises(ValidationError):
        RequestSpec(method="TRACE", url="https://example.com/api/products")


def test_fetch_options_has_non_nullable_defaults() -> None:
    options = FetchOptions()

    assert options.timeout_s == 30.0
    assert options.retries == 0
    assert options.impersonate == ""
    assert options.proxy_url == ""
