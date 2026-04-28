"""Playwright probe adapter tests that do not require Playwright."""

from ai_crawler.adapters.browser import BrowserProbeConfig, PlaywrightNetworkProbe
from ai_crawler.core.models import NetworkEvent


class FakePlaywrightDriver:
    def capture_network_events(self, url: str, wait_after_load_ms: int) -> tuple[NetworkEvent, ...]:
        return (
            NetworkEvent(
                method="GET",
                url=f"{url}/assets/app.js",
                status_code=200,
                resource_type="script",
            ),
            NetworkEvent(
                method="GET",
                url=f"{url}/api/products?page=1",
                status_code=200,
                resource_type="xhr",
            ),
        )


def test_playwright_probe_accepts_injected_driver_without_importing_playwright() -> None:
    probe = PlaywrightNetworkProbe(driver=FakePlaywrightDriver())

    evidence = probe.probe("https://example.test", goal="collect products")

    assert len(evidence.events) == 1
    assert evidence.events[0].url == "https://example.test/api/products?page=1"
    assert evidence.observations[1] == "kept 1 replay candidate event(s)"


def test_playwright_probe_accepts_probe_config_with_injected_driver() -> None:
    probe = PlaywrightNetworkProbe(
        driver=FakePlaywrightDriver(),
        config=BrowserProbeConfig(include_resource_types=("xhr",), max_events=1),
    )

    evidence = probe.probe("https://example.test", goal="inspect api")

    assert len(evidence.events) == 1
    assert evidence.events[0].url == "https://example.test/api/products?page=1"
