"""curl-cffi based HTTP fetcher adapter."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from ai_crawler.adapters.http.transport import HttpTransport
from ai_crawler.core.models import FetchOptions, FetchResponse, RequestSpec


class CurlCffiFetcher:
    """HTTP fetcher backed by curl-cffi or an injected compatible transport."""

    def __init__(self, transport: HttpTransport | None = None) -> None:
        self._transport = transport if transport is not None else self._create_default_transport()

    def fetch(self, request: RequestSpec, options: FetchOptions | None = None) -> FetchResponse:
        fetch_options = options if options is not None else FetchOptions()
        response = self._transport.request(
            method=request.method,
            url=request.url,
            headers=request.headers,
            params=request.params,
            cookies=request.cookies,
            data=request.body,
            timeout=fetch_options.timeout_s,
            impersonate=fetch_options.impersonate,
            proxy=fetch_options.proxy_url,
        )
        return FetchResponse(
            url=request.url,
            status_code=int(response.status_code),
            headers={str(key): str(value) for key, value in dict(response.headers).items()},
            body_text=str(response.text),
            elapsed_ms=_elapsed_ms(response),
        )

    @staticmethod
    def _create_default_transport() -> HttpTransport:
        try:
            from curl_cffi import requests
        except ImportError as exc:
            msg = "curl-cffi is required for CurlCffiFetcher without an injected transport"
            raise RuntimeError(msg) from exc
        return cast(HttpTransport, requests.Session())


def _elapsed_ms(response: Any) -> int:
    elapsed = getattr(response, "elapsed", 0)
    if isinstance(elapsed, timedelta):
        return round(elapsed.total_seconds() * 1000)
    if isinstance(elapsed, int | float):
        return round(elapsed * 1000)
    return 0
