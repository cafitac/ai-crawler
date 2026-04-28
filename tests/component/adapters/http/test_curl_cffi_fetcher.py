from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from ai_crawler.adapters.http.curl_cffi_fetcher import CurlCffiFetcher
from ai_crawler.core.models import FetchOptions, RequestSpec


@dataclass(frozen=True)
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    elapsed: timedelta


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def request(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return FakeResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            text='{"ok": true}',
            elapsed=timedelta(milliseconds=25),
        )


def test_fetcher_uses_injected_transport_and_normalizes_response() -> None:
    transport = FakeTransport()
    fetcher = CurlCffiFetcher(transport=transport)
    request = RequestSpec(
        method="GET",
        url="https://example.com/api/products",
        headers={"accept": "application/json"},
        params={"page": "1"},
        cookies={"session": "redacted"},
    )

    response = fetcher.fetch(request, FetchOptions(timeout_s=12.5, impersonate="chrome"))

    assert response.status_code == 200
    assert response.body_text == '{"ok": true}'
    assert response.elapsed_ms == 25
    assert transport.calls == [
        {
            "method": "GET",
            "url": "https://example.com/api/products",
            "headers": {"accept": "application/json"},
            "params": {"page": "1"},
            "cookies": {"session": "redacted"},
            "data": "",
            "timeout": 12.5,
            "impersonate": "chrome",
            "proxy": "",
        }
    ]


def test_fetcher_sends_post_body() -> None:
    transport = FakeTransport()
    fetcher = CurlCffiFetcher(transport=transport)
    request = RequestSpec(method="POST", url="https://example.com/api/search", body='{"q":"x"}')

    fetcher.fetch(request)

    assert transport.calls[0]["method"] == "POST"
    assert transport.calls[0]["data"] == '{"q":"x"}'
