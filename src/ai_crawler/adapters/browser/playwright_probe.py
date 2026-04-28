"""Playwright-backed browser network probe."""

from collections.abc import Callable
from time import sleep
from typing import Any

from ai_crawler.adapters.browser.probe import (
    BrowserNetworkProbe,
    BrowserProbeConfig,
    BrowserProbeDriver,
)
from ai_crawler.core.models import NetworkEvent


class PlaywrightNetworkProbe(BrowserNetworkProbe):
    """Browser network probe that uses Playwright when no driver is injected."""

    def __init__(
        self,
        driver: BrowserProbeDriver | None = None,
        config: BrowserProbeConfig | None = None,
    ) -> None:
        selected_driver = driver or PlaywrightNetworkDriver()
        super().__init__(driver=selected_driver, config=config)


class PlaywrightNetworkDriver:
    """Low-level Playwright driver isolated behind the browser adapter boundary."""

    def capture_network_events(
        self,
        url: str,
        wait_after_load_ms: int,
    ) -> tuple[NetworkEvent, ...]:
        sync_playwright = _load_sync_playwright()
        events: list[NetworkEvent] = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.on("response", _response_handler(events))
                page.goto(url, wait_until="networkidle")
                if wait_after_load_ms > 0:
                    sleep(wait_after_load_ms / 1000)
            finally:
                browser.close()

        return tuple(events)


def _load_sync_playwright() -> Callable[[], Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        msg = "Install browser support with `pip install 'ai-crawler[browser]'`."
        raise RuntimeError(msg) from error
    return sync_playwright


def _response_handler(events: list[NetworkEvent]) -> Callable[[Any], None]:
    def handle_response(response: Any) -> None:
        request = response.request
        events.append(
            NetworkEvent(
                method=request.method,
                url=response.url,
                status_code=response.status,
                resource_type=request.resource_type,
            )
        )

    return handle_response
