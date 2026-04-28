"""Small stdlib HTTP fixture server for deterministic integration tests."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import TracebackType
from urllib.parse import parse_qs, urlparse

from ai_crawler.testing.fixture_site.scenarios import (
    FixtureResponse,
    cloudflare_like_challenge,
    not_found,
    products_api,
    products_page,
)


class FixtureSite:
    """Context-managed local fixture HTTP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self._host = host
        self._server = ThreadingHTTPServer((host, port), FixtureRequestHandler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        port = self._server.server_port
        return f"http://{self._host}:{port}"

    def __enter__(self) -> FixtureSite:
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


class FixtureRequestHandler(BaseHTTPRequestHandler):
    """Routes fixture HTTP requests to deterministic scenario responses."""

    server_version = "AiCrawlerFixture/0.1"

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        response = route_get(parsed_url.path, parse_qs(parsed_url.query))
        self._write_response(response)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_response(self, response: FixtureResponse) -> None:
        body = response.body.encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("content-type", response.content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def route_get(path: str, query: dict[str, list[str]]) -> FixtureResponse:
    """Pure routing function for fixture GET requests."""

    if path == "/products":
        return products_page()
    if path == "/api/products":
        return products_api(_first_query_value(query, "page", default="1"))
    if path == "/challenge/cloudflare-like":
        return cloudflare_like_challenge()
    return not_found()


def _first_query_value(query: dict[str, list[str]], key: str, default: str) -> str:
    values = query.get(key, [])
    if not values:
        return default
    return values[0]
